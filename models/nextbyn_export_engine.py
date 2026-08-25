# -*- coding: utf-8 -*-
"""
Motor de exportación Nextbyn - Cumple con el instructivo oficial.
Documentación: "CSV - Instructivo de implementacion CSV V2.4.2"
(Manual de implementación de interfaces de integración a Nextbyn CSV)

Formato nombre archivo: {Entidad}00EEEEAAAAMMDDHHMMSS.csv
- EEEE = ID empresa provisto por Nextbyn (se completa con ceros a 6: "00"+EEEE)
- AAAAMMDDHHMMSS = Timestamp de generación
- Separador = ;
- Primera fila = Headers (respetar mayúsculas/minúsculas)
- Extensión .csv siempre en minúscula
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import csv
import io
from datetime import datetime

_logger = logging.getLogger(__name__)


class NextbynExportEngine(models.AbstractModel):
    """
    Motor de exportación que implementa la generación de los 7 CSVs
    según el instructivo oficial Nextbyn V2.4.2.

    Archivos: Articulos, Clientes, PersonalComercial, RutasDeVenta,
    ClientesRuta, StockFisico, Comprobantes.
    """
    _name = 'nextbyn.export.engine'
    _description = 'Motor Exportación Nextbyn'

    # =========================================================================
    # CONSTANTES SEGÚN INSTRUCTIVO V2.4.2
    # =========================================================================

    SEPARATOR = ';'
    ENCODING = 'utf-8'

    # El instructivo usa DD/MM/YYYY en TODAS las fechas de los CSVs
    DATE_FORMAT_CSV = '%d/%m/%Y'
    TIME_FORMAT = '%H:%M:%S'

    # Constantes de fechas según instructivo
    FECHA_DESDE_DEFAULT = '01/01/1900'
    FECHA_HASTA_DEFAULT = '31/12/9999'
    VENCIMIENTO_LOTE_DEFAULT = '31/12/9999'

    # =========================================================================
    # API PRINCIPAL
    # =========================================================================

    @api.model
    def export_all(self, connector, date_from=None, date_to=None):
        """
        Ejecuta exportación completa de las 7 entidades.
        Retorna lista de (filename, content, row_count).

        Lógica de negocio:
        - Productos: todos los productos cuyo proveedor sea el partner Softys
          configurado en el conector (softys_partner_id).
        - Clientes: todos los clientes que tengan al menos una factura de venta
          posted con líneas de esos productos.
        """
        results = []

        # Validar que esté configurado el proveedor Softys
        if not connector.softys_partner_id:
            raise UserError(_(
                'No se configuró el Proveedor Softys en el conector. '
                'Configúrelo para determinar qué productos y clientes exportar.'
            ))

        # Artículos: productos cuyo proveedor es Softys
        product_ids = self._get_softys_product_ids(connector)
        products = self.env['product.product'].browse(product_ids)
        if products:
            results.append(self.generate_articulos(connector, products))

        # Clientes: clientes con ventas de productos Softys
        customer_ids = self._get_softys_customer_ids(product_ids)
        partners = self.env['res.partner'].browse(customer_ids)
        if partners:
            results.append(self.generate_clientes(connector, partners))

        # Personal Comercial: se genera automáticamente con los vendedores
        # reales (invoice_user_id) de las ventas de productos Softys.
        # No requiere configuración manual.
        if product_ids:
            all_softys_invoices = self.env['account.move'].search([
                ('move_type', 'in', ['out_invoice', 'out_refund']),
                ('state', '=', 'posted'),
                ('invoice_line_ids.product_id', 'in', product_ids),
            ])
            if all_softys_invoices:
                results.append(self.generate_personal_comercial(connector, all_softys_invoices))

        # Rutas de Venta
        if connector.ruta_venta_ids:
            results.append(self.generate_rutas_de_venta(connector))

        # Clientes Ruta: TODOS los clientes del archivo Clientes deben estar
        # (instructivo: "todos los clientes que estén en el archivo Clientes
        # deben estar en este archivo"). Sin ruta -> ruta por defecto.
        if partners:
            results.append(self.generate_clientes_ruta(connector, partners))

        # Stock Físico: todos los artículos del maestro por depósito,
        # incluso sin stock (instructivo: N artículos por cada depósito).
        products_activos = products.filtered('active')
        if products_activos:
            results.append(self.generate_stock_fisico(connector, products_activos))

        # Comprobantes: facturas de venta con productos Softys
        if date_from and date_to:
            invoices = self.env['account.move'].search([
                ('move_type', 'in', ['out_invoice', 'out_refund']),
                ('state', '=', 'posted'),
                ('invoice_date', '>=', date_from),
                ('invoice_date', '<=', date_to),
                ('invoice_line_ids.product_id', 'in', product_ids),
            ])
            if invoices:
                results.append(self.generate_comprobantes(connector, invoices, product_ids))

        return results

    # =========================================================================
    # UTILIDADES DE DATOS
    # =========================================================================

    def _get_softys_product_ids(self, connector):
        """
        Devuelve los IDs de product.product cuyo proveedor (seller_ids)
        coincide con el partner Softys configurado en el conector.
        """
        if not connector.softys_partner_id:
            return []

        supplier_infos = self.env['product.supplierinfo'].search([
            ('partner_id', '=', connector.softys_partner_id.id),
        ])
        template_ids = supplier_infos.mapped('product_tmpl_id').ids

        if not template_ids:
            return []

        products = self.env['product.product'].search([
            ('product_tmpl_id', 'in', template_ids),
            ('active', 'in', [True, False]),
        ])
        return products.ids

    def _get_softys_customer_ids(self, product_ids, date_from=None, date_to=None):
        """
        Devuelve los IDs de res.partner que tienen al menos una factura
        de venta (out_invoice/out_refund) en estado posted con líneas
        de los productos indicados.
        """
        if not product_ids:
            return []

        domain = [
            ('move_type', 'in', ['out_invoice', 'out_refund']),
            ('state', '=', 'posted'),
            ('invoice_line_ids.product_id', 'in', product_ids),
        ]
        if date_from:
            domain.append(('invoice_date', '>=', date_from))
        if date_to:
            domain.append(('invoice_date', '<=', date_to))

        invoices = self.env['account.move'].search(domain)
        return invoices.mapped('partner_id').ids

    # =========================================================================
    # UTILIDADES DE FORMATO
    # =========================================================================

    def _get_timestamp(self):
        """Genera timestamp para nombre de archivo: AAAAMMDDHHMMSS"""
        return datetime.now().strftime('%Y%m%d%H%M%S')

    def _get_filename(self, entity_name, company_code):
        """
        Genera nombre de archivo según instructivo V2.4.2:
        NombreArchivo + "00" + EEEE + AAAAMMDDHHMMSS + .csv
        (zfill(6) equivale a "00" + EEEE para códigos de 4 dígitos)
        """
        timestamp = self._get_timestamp()
        code = str(company_code).zfill(6)
        return f"{entity_name}{code}{timestamp}.csv"

    def _format_bool(self, value, format_type='01'):
        """
        Formatea booleano según tipo requerido.
        format_type: '01', 'SINO_upper', 'YESNO_upper', 'sino_lower', 'yesno_lower'
        """
        if format_type == '01':
            return '1' if value else '0'
        elif format_type == 'SINO_upper':
            return 'SI' if value else 'NO'
        elif format_type == 'YESNO_upper':
            return 'YES' if value else 'NO'
        elif format_type == 'sino_lower':
            return 'si' if value else 'no'
        elif format_type == 'yesno_lower':
            return 'yes' if value else 'no'
        return '1' if value else '0'

    def _format_date(self, date_value):
        """
        Formatea fecha según instructivo V2.4.2: DD/MM/YYYY.
        Acepta date, datetime o string (el string se normaliza a DD/MM/YYYY).
        """
        if not date_value:
            return ''

        if isinstance(date_value, str):
            value = date_value.strip()
            for fmt in ('%d/%m/%Y', '%Y/%m/%d', '%Y-%m-%d', '%d-%m-%Y'):
                try:
                    return datetime.strptime(value, fmt).strftime(self.DATE_FORMAT_CSV)
                except ValueError:
                    continue
            # Si no matchea ningún formato conocido, se devuelve tal cual
            return value

        return date_value.strftime(self.DATE_FORMAT_CSV)

    def _format_decimal(self, value, decimals=6):
        """
        Formatea número decimal sin ceros a la derecha innecesarios.
        Ej: 2.0 -> '2', 0.5702 -> '0.5702', 25000 -> '25000'
        """
        if value is None:
            return '0'
        formatted = f'{float(value):.{decimals}f}'.rstrip('0').rstrip('.')
        return formatted if formatted else '0'

    def _format_integer(self, value):
        """Formatea número entero."""
        if value is None or value == '':
            return '0'
        try:
            return str(int(value))
        except (ValueError, TypeError):
            # Si viene texto no numérico (ej: código depósito 'WH'), devolver 0
            _logger.warning(f'Valor no numérico para campo entero: {value!r}')
            return '0'

    def _clean_text(self, text, max_length=None):
        """Limpia texto para CSV."""
        if not text:
            return ''
        result = str(text).strip()
        # Reemplazar separadores que podrían romper el CSV
        result = result.replace(';', ',').replace('\n', ' ').replace('\r', '')
        if max_length and len(result) > max_length:
            result = result[:max_length]
        return result

    def _create_csv_content(self, headers, rows):
        """
        Crea contenido CSV con headers y filas.
        Según instructivo: separador ; y primera fila con nombres de campos.
        """
        output = io.StringIO()
        writer = csv.writer(
            output,
            delimiter=self.SEPARATOR,
            quotechar='"',
            quoting=csv.QUOTE_MINIMAL,
            lineterminator='\n'
        )

        # Primera fila: headers (según instructivo)
        writer.writerow(headers)

        # Filas de datos
        for row in rows:
            writer.writerow(row)

        return output.getvalue()

    # =========================================================================
    # GENERADORES DE ARCHIVOS - SEGÚN INSTRUCTIVO V2.4.2
    # =========================================================================

    def generate_articulos(self, connector, products):
        """
        Genera Articulos CSV según instructivo V2.4.2.

        Columnas (ejemplo oficial):
        - CodigoArticulo (Número, obligatorio, único)
        - DescripcionArticulo (Texto 50, obligatorio)
        - Anulado (Booleano, obligatorio)
        - UnidadesXBulto (Número, obligatorio)
        - ValorUMedida (Decimal 8.4, obligatorio) - total litros/kilos del bulto
        """
        headers = [
            'CodigoArticulo',
            'DescripcionArticulo',
            'Anulado',
            'UnidadesXBulto',
            'ValorUMedida',
        ]

        rows = []
        for product in products:
            if not product.x_softys_valor_umedida:
                _logger.warning(
                    f'Producto {product.id} ({product.name}) sin Valor Unidad '
                    f'de Medida (ValorUMedida) - se exporta en 0'
                )
            row = [
                self._format_integer(product.id),  # CodigoArticulo
                self._clean_text(product.name, 50),  # DescripcionArticulo
                self._format_bool(not product.active, 'SINO_upper'),  # Anulado (NO/SI)
                self._format_integer(product.x_softys_unidades_bulto or 1),  # UnidadesXBulto
                self._format_decimal(product.x_softys_valor_umedida or 0, 4),  # ValorUMedida
            ]
            rows.append(row)

        filename = self._get_filename('Articulos', connector.company_code)
        content = self._create_csv_content(headers, rows)

        return filename, content, len(rows)

    def generate_clientes(self, connector, partners):
        """
        Genera Clientes CSV según instructivo V2.4.2.

        Campos clave únicos: CodigoSucursal, CodigoCliente.

        Notas:
        - CodListaPrecio: debe estar pero va vacío (según instructivo/mail).
        - CodigoLocalidad/DescripcionLocalidad/CodigoProvincia/DescProvincia:
          según Anexo de Ciudades Argentinas (catálogo softys.localidad).
        """
        headers = [
            'CodigoSucursal',
            'CodigoCliente',
            'Nombre',
            'Domicilio',
            'NumeroCuit',
            'IdCanalAgrupa',
            'DescCanalAgrupa',
            'IdSubCanalAgrupa',
            'DescSubCanalAgrupa',
            'FechaAlta',
            'Anulado',
            'TipoContribuyente',
            'CodListaPrecio',
            'IdTipoDocumentoCliente',
            'CodigoLocalidad',
            'DescripcionLocalidad',
            'CodigoProvincia',
            'DescProvincia',
        ]

        rows = []
        for partner in partners:
            # Canal / Subcanal (si no hay subcanal, se repite el canal)
            canal = partner.x_softys_canal_id
            subcanal = partner.x_softys_subcanal_id
            if not canal:
                _logger.warning(
                    f'Cliente {partner.id} ({partner.name}) sin canal Nextbyn asignado'
                )
            id_canal = self._format_integer(canal.codigo) if canal else ''
            desc_canal = self._clean_text(canal.nombre, 100) if canal else ''
            if subcanal:
                id_subcanal = self._format_integer(subcanal.codigo)
                desc_subcanal = self._clean_text(subcanal.nombre, 100)
            else:
                id_subcanal = id_canal
                desc_subcanal = desc_canal

            # Localidad / Provincia según Anexo (con fallback a defaults del conector)
            localidad = partner.x_softys_localidad_anexo_id
            if localidad:
                cod_localidad = str(localidad.id_localidad)
                desc_localidad = self._clean_text(localidad.nombre, 100)
                cod_provincia = str(localidad.id_provincia)
                desc_provincia = self._clean_text(localidad.provincia_nombre, 50)
            else:
                _logger.warning(
                    f'Cliente {partner.id} ({partner.name}) sin localidad del '
                    f'Anexo Nextbyn - se usan defaults del conector'
                )
                cod_localidad = self._clean_text(connector.codigo_localidad_default or '', 20)
                desc_localidad = self._clean_text(
                    partner.city or connector.localidad_default or '', 100)
                cod_provincia = self._clean_text(connector.provincia_codigo_default or '', 50)
                desc_provincia = self._clean_text(
                    partner.state_id.name or connector.provincia_nombre_default or '', 50)

            row = [
                self._format_integer(connector.codigo_sucursal or 1),  # CodigoSucursal
                self._clean_text(partner.id, 50),  # CodigoCliente
                self._clean_text(partner.name, 100),  # Nombre
                self._clean_text(self._get_full_address(partner), 100),  # Domicilio
                self._clean_text(partner.x_softys_numero_documento or '', 50),  # NumeroCuit
                id_canal,  # IdCanalAgrupa
                desc_canal,  # DescCanalAgrupa
                id_subcanal,  # IdSubCanalAgrupa
                desc_subcanal,  # DescSubCanalAgrupa
                self._format_date(partner.create_date) or self.FECHA_DESDE_DEFAULT,  # FechaAlta
                self._format_bool(not partner.active, 'SINO_upper'),  # Anulado (NO/SI)
                self._get_tipo_contribuyente(partner),  # TipoContribuyente
                '',  # CodListaPrecio - debe ir vacío según instructivo
                self._get_tipo_documento(partner),  # IdTipoDocumentoCliente
                cod_localidad,  # CodigoLocalidad
                desc_localidad,  # DescripcionLocalidad
                cod_provincia,  # CodigoProvincia
                desc_provincia,  # DescProvincia
            ]
            rows.append(row)

        filename = self._get_filename('Clientes', connector.company_code)
        content = self._create_csv_content(headers, rows)

        return filename, content, len(rows)

    def generate_personal_comercial(self, connector, invoices):
        """
        Genera PersonalComercial CSV según instructivo V2.4.2.

        Se genera automáticamente con los vendedores reales: usuarios de Odoo
        (invoice_user_id) que figuran en las ventas de productos Softys.

        - CodigoPersonal = x_softys_codigo del empleado si está cargado,
          si no, el ID del usuario de Odoo (res.users).
        - Cargo = x_softys_cargo del empleado, si no 'V' (Vendedor).
        - CodigoPersonalSuperior = usuario del jefe directo (hr.employee.parent_id).
        - CodigoFuerza = x_softys_codigo_fuerza del empleado, si no el del conector.
        """
        headers = [
            'CodigoSucursal',
            'CodigoPersonal',
            'Descripcion',
            'Cargo',
            'Anulado',
            'CodigoPersonalSuperior',
            'CodigoFuerza',
        ]

        rows = []
        users = invoices.mapped('invoice_user_id')
        for user in users:
            employee = user.employee_id
            codigo_personal = self._get_codigo_personal(user)

            # Superior: usuario vinculado al jefe directo del empleado
            superior = ''
            if employee and employee.parent_id and employee.parent_id.user_id:
                superior = str(employee.parent_id.user_id.id)

            row = [
                self._format_integer(connector.codigo_sucursal or 1),  # CodigoSucursal
                self._format_integer(codigo_personal),  # CodigoPersonal
                self._clean_text(user.name, 50),  # Descripcion
                (employee.x_softys_cargo if employee and employee.x_softys_cargo else 'V'),  # Cargo
                self._format_bool(not user.active, 'SINO_upper'),  # Anulado (NO/SI)
                superior,  # CodigoPersonalSuperior (o vacío)
                self._format_integer(
                    (employee.x_softys_codigo_fuerza if employee and employee.x_softys_codigo_fuerza else 0)
                    or connector.codigo_fuerza or 1),  # CodigoFuerza
            ]
            rows.append(row)

        filename = self._get_filename('PersonalComercial', connector.company_code)
        content = self._create_csv_content(headers, rows)

        return filename, content, len(rows)

    def generate_rutas_de_venta(self, connector):
        """
        Genera RutasDeVenta CSV según instructivo V2.4.2.

        Campo clave único: CodigoRuta.
        Una ruta no puede estar asociada a más de 1 vendedor.
        FechaDesde: DD/MM/YYYY (01/01/1900 si no se tiene el dato).
        """
        headers = [
            'CodigoSucursal',
            'CodigoFuerza',
            'CodigoModoAtencion',
            'CodigoRuta',
            'DescripcionRuta',
            'CodigoPersonal',
            'FechaDesde',
            'Periodicidad',
            'Semana',
            'AtiendeLunes',
            'AtiendeMartes',
            'AtiendeMiercoles',
            'AtiendeJueves',
            'AtiendeViernes',
            'AtiendeSabado',
            'AtiendeDomingo',
        ]

        rows = []
        for ruta in connector.ruta_venta_ids:
            row = [
                self._format_integer(connector.codigo_sucursal or 1),  # CodigoSucursal
                self._format_integer(connector.codigo_fuerza or 1),  # CodigoFuerza
                self._clean_text(connector.codigo_modo_atencion or 'PRE', 5),  # CodigoModoAtencion
                self._format_integer(ruta.codigo_ruta),  # CodigoRuta
                self._clean_text(ruta.descripcion_ruta, 50),  # DescripcionRuta
                self._format_integer(ruta.codigo_personal),  # CodigoPersonal
                self._format_date(ruta.fecha_desde) or self.FECHA_DESDE_DEFAULT,  # FechaDesde
                self._format_integer(ruta.periodicidad or 1),  # Periodicidad
                self._format_integer(ruta.semana or 1),  # Semana
                self._format_bool(ruta.atiende_lunes, '01'),  # AtiendeLunes
                self._format_bool(ruta.atiende_martes, '01'),  # AtiendeMartes
                self._format_bool(ruta.atiende_miercoles, '01'),  # AtiendeMiercoles
                self._format_bool(ruta.atiende_jueves, '01'),  # AtiendeJueves
                self._format_bool(ruta.atiende_viernes, '01'),  # AtiendeViernes
                self._format_bool(ruta.atiende_sabado, '01'),  # AtiendeSabado
                self._format_bool(ruta.atiende_domingo, '01'),  # AtiendeDomingo
            ]
            rows.append(row)

        filename = self._get_filename('RutasDeVenta', connector.company_code)
        content = self._create_csv_content(headers, rows)

        return filename, content, len(rows)

    def generate_clientes_ruta(self, connector, partners):
        """
        Genera ClientesRuta CSV según instructivo V2.4.2.

        TODOS los clientes del archivo Clientes deben estar en este archivo.
        Si el cliente no tiene ruta asignada, se usa la ruta por defecto
        del conector (codigo_ruta_default).
        Sin historia: FechaDesde = 01/01/1900, FechaHasta = 31/12/9999.
        """
        headers = [
            'CodigoSucursal',
            'CodigoFuerza',
            'CodigoModoAtencion',
            'CodigoCliente',
            'CodigoRuta',
            'FechaDesde',
            'FechaHasta',
        ]

        rows = []
        for partner in partners:
            codigo_ruta = partner.x_softys_codigo_ruta
            if not codigo_ruta:
                codigo_ruta = connector.codigo_ruta_default or '00'

            row = [
                self._format_integer(connector.codigo_sucursal or 1),  # CodigoSucursal
                self._format_integer(connector.codigo_fuerza or 1),  # CodigoFuerza
                self._clean_text(connector.codigo_modo_atencion or 'PRE', 5),  # CodigoModoAtencion
                self._clean_text(partner.id, 50),  # CodigoCliente
                self._format_integer(codigo_ruta),  # CodigoRuta
                self.FECHA_DESDE_DEFAULT,  # FechaDesde (01/01/1900 sin historia)
                self.FECHA_HASTA_DEFAULT,  # FechaHasta (31/12/9999 activo)
            ]
            rows.append(row)

        filename = self._get_filename('ClientesRuta', connector.company_code)
        content = self._create_csv_content(headers, rows)

        return filename, content, len(rows)

    def generate_stock_fisico(self, connector, products):
        """
        Genera StockFisico CSV según instructivo V2.4.2.

        Reglas del instructivo:
        - Foto del stock del día de la transmisión.
        - Debe tener TODOS los artículos habilitados del Maestro de Artículos
          por cada depósito informado, incluso si no tienen stock (cantidad 0).
        - Sin dato de lote: VencimientoLote = 31/12/9999.
        - Fechas en DD/MM/YYYY.
        - CodigoDeposito numérico.
        """
        headers = [
            'CodigoDeposito',
            'CodigoArticulo',
            'VencimientoLote',
            'CantidadDecimal',
            'FechaStock',
        ]

        today_str = fields.Date.today().strftime(self.DATE_FORMAT_CSV)

        # Depósitos: almacenes marcados para exportar. Si no hay ninguno
        # configurado, se usa un único depósito con el código del conector
        # sobre todas las ubicaciones internas.
        warehouses = self.env['stock.warehouse'].search([
            ('x_softys_exportar', '=', True),
        ])

        # (codigo_deposito, location_ids)
        depositos = []
        if warehouses:
            for wh in warehouses:
                code = wh.x_softys_codigo_deposito or connector.codigo_deposito or '1'
                location_ids = self.env['stock.location'].search([
                    ('id', 'child_of', wh.view_location_id.id),
                    ('usage', '=', 'internal'),
                ]).ids
                depositos.append((code, location_ids))
        else:
            location_ids = self.env['stock.location'].search([
                ('usage', '=', 'internal'),
            ]).ids
            depositos.append((connector.codigo_deposito or '1', location_ids))

        rows = []
        for codigo_deposito, location_ids in depositos:
            # Stock agregado por producto en este depósito
            stock_by_product = {}
            if location_ids:
                groups = self.env['stock.quant'].read_group(
                    domain=[
                        ('location_id', 'in', location_ids),
                        ('product_id', 'in', products.ids),
                    ],
                    fields=['quantity:sum'],
                    groupby=['product_id'],
                    lazy=False,
                )
                for group in groups:
                    stock_by_product[group['product_id'][0]] = group['quantity']

            # Una fila por artículo del maestro (aunque no tenga stock)
            for product in products:
                cantidad = stock_by_product.get(product.id, 0.0)
                row = [
                    self._format_integer(codigo_deposito),  # CodigoDeposito
                    self._format_integer(product.id),  # CodigoArticulo
                    self.VENCIMIENTO_LOTE_DEFAULT,  # VencimientoLote (sin lote: 31/12/9999)
                    self._format_decimal(cantidad, 6),  # CantidadDecimal
                    today_str,  # FechaStock
                ]
                rows.append(row)

        filename = self._get_filename('StockFisico', connector.company_code)
        content = self._create_csv_content(headers, rows)

        return filename, content, len(rows)

    def generate_comprobantes(self, connector, invoices, product_ids=None):
        """
        Genera Comprobantes CSV según instructivo V2.4.2.

        Valor único: TipoComprobante + LetraComprobante + SerieComprobante +
        NumeroComprobante + NumeroLinea (no puede repetirse).

        Reglas:
        - EsVenta siempre YES (interno, según instructivo).
        - NC/devoluciones: solo CantidadDecimal en negativo.
        - PrecioUnitarioBruto nunca 0 (precio de lista sin descuento ni impuestos).
        - Bonificacion = porcentaje de descuento.
        - Fechas DD/MM/YYYY.
        """
        headers = [
            'CodigoEmpresaFactura',
            'TipoComprobante',
            'LetraComprobante',
            'SerieComprobante',
            'NumeroComprobante',
            'NumeroLinea',
            'CodigoFuerza',
            'EsVenta',
            'CodigoArticulo',
            'DescripcionArticulo',
            'UnidadesPorBulto',
            'CantidadDecimal',
            'PrecioUnitarioBruto',
            'Bonificacion',
            'FechaPedido',
            'FechaComprobante',
            'CodigoCliente',
            'CodigoSucursal',
            'NombreCliente',
            'TipoContribuyente',
            'Anulado',
            'CodigoPersonal',
        ]

        rows = []
        product_ids_set = set(product_ids or [])

        for invoice in invoices:
            # Parsear número de factura argentina
            tipo, letra, serie, numero = self._parse_invoice_number(invoice)
            codigo_personal = self._get_vendedor_code(invoice, connector)

            line_num = 0
            lines = invoice.invoice_line_ids.filtered(lambda l: l.product_id)
            if product_ids_set:
                lines = lines.filtered(lambda l: l.product_id.id in product_ids_set)

            for line in lines:
                line_num += 1

                # Cantidad: positiva para facturas, negativa para NC.
                # Solo la cantidad va en negativo (el resto se calcula solo).
                cantidad = line.quantity
                if invoice.move_type == 'out_refund':
                    cantidad = -abs(cantidad)

                # PrecioUnitarioBruto nunca debe ser 0 (instructivo).
                # Es el precio de lista facturado sin descuento ni impuestos.
                precio = line.price_unit
                if not precio:
                    precio = line.product_id.lst_price or 0
                    _logger.warning(
                        f'Línea sin precio unitario en {invoice.name} '
                        f'(producto {line.product_id.id}) - se usa precio de lista'
                    )

                row = [
                    self._format_integer(connector.company_code),  # CodigoEmpresaFactura
                    self._clean_text(tipo, 6),  # TipoComprobante
                    self._clean_text(letra, 10),  # LetraComprobante
                    self._format_integer(serie),  # SerieComprobante
                    self._format_integer(numero),  # NumeroComprobante
                    self._format_integer(line_num),  # NumeroLinea
                    self._format_integer(connector.codigo_fuerza or 1),  # CodigoFuerza
                    self._format_bool(True, 'YESNO_upper'),  # EsVenta - siempre YES
                    self._format_integer(line.product_id.id),  # CodigoArticulo
                    self._clean_text(line.product_id.name, 50),  # DescripcionArticulo
                    self._format_integer(line.product_id.x_softys_unidades_bulto or 1),  # UnidadesPorBulto
                    self._format_decimal(cantidad, 6),  # CantidadDecimal
                    self._format_decimal(precio, 6),  # PrecioUnitarioBruto
                    self._format_decimal(line.discount or 0, 3),  # Bonificacion
                    self._format_date(invoice.invoice_date),  # FechaPedido
                    self._format_date(invoice.invoice_date),  # FechaComprobante
                    self._clean_text(invoice.partner_id.id, 50),  # CodigoCliente
                    self._format_integer(connector.codigo_sucursal or 1),  # CodigoSucursal
                    self._clean_text(invoice.partner_id.name, 100),  # NombreCliente
                    self._get_tipo_contribuyente(invoice.partner_id),  # TipoContribuyente
                    self._format_bool(False, 'SINO_upper'),  # Anulado (solo posted: NO)
                    self._format_integer(codigo_personal),  # CodigoPersonal
                ]
                rows.append(row)

        filename = self._get_filename('Comprobantes', connector.company_code)
        content = self._create_csv_content(headers, rows)

        return filename, content, len(rows)

    # =========================================================================
    # MÉTODOS AUXILIARES
    # =========================================================================

    def _get_full_address(self, partner):
        """Construye dirección completa del partner."""
        parts = []
        if partner.street:
            parts.append(partner.street)
        if partner.street2:
            parts.append(partner.street2)
        if partner.city:
            parts.append(partner.city)
        return ', '.join(parts) if parts else ''

    def _get_tipo_contribuyente(self, partner):
        """
        Obtiene código de tipo contribuyente (2 caracteres).
        Según instructivo: CF / EX / RI / MT / AU / NC / RN.
        """
        afip_type = partner.l10n_ar_afip_responsibility_type_id
        if afip_type:
            code = afip_type.code
            mapping = {
                '1': 'RI',   # IVA Responsable Inscripto
                '4': 'EX',   # IVA Sujeto Exento
                '5': 'CF',   # Consumidor Final
                '6': 'MT',   # Responsable Monotributo
                '9': 'NC',   # Cliente del Exterior -> No Categorizado
                '13': 'RN',  # Monotributista Social -> aproximación
            }
            return mapping.get(code, 'CF')
        return 'CF'  # Default: Consumidor Final

    def _get_tipo_documento(self, partner):
        """
        Obtiene código de tipo de documento.
        80 = CUIT, 86 = CUIL, 87 = CDI, 89 = LE, 90 = LC, 96 = DNI.
        """
        doc_type = partner.l10n_latam_identification_type_id
        if doc_type:
            name = doc_type.name.lower()
            if 'cuit' in name:
                return '80'
            elif 'cuil' in name:
                return '86'
            elif 'cdi' in name:
                return '87'
            elif name in ('le',):
                return '89'
            elif name in ('lc',):
                return '90'
            elif 'dni' in name:
                return '96'
        return '96'  # Default: DNI

    def _parse_invoice_number(self, invoice):
        """
        Parsea el comprobante para Nextbyn.
        Retorna: (tipo, letra, serie, numero)

        Formatos soportados:
        - Fiscal AR: 'FA-A 00003-00002620' (con l10n_latam_document_type)
        - Legacy/demo: 'D3FD/2026/00122' (sin tipo de documento fiscal)
        """
        import re
        name = invoice.name or ''

        # Valores por defecto
        tipo = 'FCVTA'
        letra = 'A'
        serie = 0
        numero = 0

        if invoice.l10n_latam_document_type_id:
            doc_code = invoice.l10n_latam_document_type_id.code or ''
            # Mapear códigos AFIP a tipos Nextbyn
            if doc_code in ('1', '6', '11'):  # Facturas
                tipo = 'FCVTA'
            elif doc_code in ('3', '8', '13'):  # Notas de Crédito
                tipo = 'NCRED'
            elif doc_code in ('2', '7', '12'):  # Notas de Débito
                tipo = 'NDEB'

            # Extraer letra
            doc_name = invoice.l10n_latam_document_type_id.name or ''
            if ' A' in doc_name or doc_name.endswith('A'):
                letra = 'A'
            elif ' B' in doc_name or doc_name.endswith('B'):
                letra = 'B'
            elif ' C' in doc_name or doc_name.endswith('C'):
                letra = 'C'
        else:
            # Sin tipo fiscal (legacy/demo): deducir del prefijo del nombre
            prefix = name.upper()
            if prefix.startswith('NC'):
                tipo = 'NCRED'
            elif prefix.startswith('ND'):
                tipo = 'NDEB'

        # Formato fiscal: 'FA-A 00003-00002620'
        m = re.search(r'(\d{4,5})\s*-\s*(\d{1,8})\s*$', name)
        if m:
            serie = int(m.group(1))
            numero = int(m.group(2))
        else:
            # Formato legacy/demo: 'D3FD/2026/00122'
            m = re.search(r'/(\d{4})/(\d+)\s*$', name)
            if m:
                numero = int(m.group(2))
                # Serie ficticia estable por diario (9000+id) para no colisionar
                # con puntos de venta fiscales reales
                serie = 9000 + (invoice.journal_id.id or 0)
            else:
                nums = re.findall(r'\d+', name)
                if nums:
                    numero = int(nums[-1])

        if not serie:
            serie = 1
        if not numero:
            # Último recurso: garantizar unicidad con el ID interno
            numero = invoice.id
            _logger.warning(
                f'No se pudo parsear número de comprobante {name!r} - '
                f'se usa ID interno {invoice.id}'
            )

        return tipo, letra, serie, numero

    def _format_time(self, datetime_value):
        """Formatea hora."""
        if not datetime_value:
            return '00:00:00'
        return datetime_value.strftime(self.TIME_FORMAT)

    def _get_codigo_personal(self, user):
        """
        Código de personal (CodigoPersonal) para un usuario vendedor.
        Prioridad: x_softys_codigo del empleado vinculado > ID del usuario.
        """
        employee = user.employee_id
        if employee and employee.x_softys_codigo:
            return employee.x_softys_codigo
        return user.id

    def _get_vendedor_code(self, invoice, connector):
        """
        CodigoPersonal para una factura: el vendedor real de la venta.
        Prioridad: campo Vendedor de la factura (x_softys_vendedor_id) >
        vendedor de la factura (invoice_user_id).
        """
        if invoice.x_softys_vendedor_id:
            employee = invoice.x_softys_vendedor_id
            return employee.x_softys_codigo or employee.id

        if invoice.invoice_user_id:
            return self._get_codigo_personal(invoice.invoice_user_id)

        _logger.warning(f'Factura {invoice.name} sin vendedor - CodigoPersonal=0')
        return 0
