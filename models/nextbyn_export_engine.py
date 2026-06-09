# -*- coding: utf-8 -*-
"""
Motor de exportación Nextbyn - Cumple rigurosamente con la documentación oficial.
Documentación: Manual de implementación de interfases de integración a Nextbyn
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import csv
import io
import os
from datetime import datetime, timedelta
import base64

_logger = logging.getLogger(__name__)


class NextbynExportEngine(models.AbstractModel):
    """
    Motor de exportación que implementa la generación de CSVs según
    especificación oficial Nextbyn.
    
    Formato nombre archivo: {Entidad}EEEEEEAAAAMMDDHHMMSS.csv
    - EEEEEE = ID empresa (6 dígitos)
    - AAAAMMDDHHMMSS = Timestamp
    - Separador = ;
    - Primera fila = Headers
    """
    _name = 'nextbyn.export.engine'
    _description = 'Motor Exportación Nextbyn'
    
    # =========================================================================
    # CONSTANTES Y CONFIGURACIÓN
    # =========================================================================
    
    SEPARATOR = ';'
    ENCODING = 'utf-8'
    
    # Formatos de fecha según documentación
    DATE_FORMAT_YYYYMMDD = '%Y/%m/%d'  # yyyy/MM/dd
    DATE_FORMAT_DDMMYYYY = '%d/%m/%Y'  # dd/MM/yyyy
    DATETIME_FORMAT = '%Y/%m/%d %H:%M:%S'
    TIME_FORMAT = '%H:%M:%S'
    
    # =========================================================================
    # API PRINCIPAL
    # =========================================================================
    
    @api.model
    def export_all(self, connector, date_from=None, date_to=None):
        """
        Ejecuta exportación completa de todas las entidades.
        Retorna lista de (filename, content, row_count).
        """
        results = []
        
        # Artículos
        products = self.env['product.product'].search([
            ('x_softys_producto', '=', True),
            ('active', 'in', [True, False]),
        ])
        if products:
            results.append(self.generate_articulos(connector, products))
        
        # Clientes
        partners = self.env['res.partner'].search([
            ('x_softys_exportar', '=', True),
            ('customer_rank', '>', 0),
        ])
        if partners:
            results.append(self.generate_clientes(connector, partners))
        
        # Personal Comercial
        if connector.personal_comercial_ids:
            results.append(self.generate_personal_comercial(connector))
        
        # Rutas de Venta
        if connector.ruta_venta_ids:
            results.append(self.generate_rutas_de_venta(connector))
        
        # Clientes Ruta
        partners_ruta = self.env['res.partner'].search([
            ('x_softys_exportar', '=', True),
            ('customer_rank', '>', 0),
        ])
        if partners_ruta:
            results.append(self.generate_clientes_ruta(connector, partners_ruta))
        
        # Stock Físico
        quants = self.env['stock.quant'].search([
            ('quantity', '>', 0),
            ('location_id.usage', '=', 'internal'),
        ])
        if quants:
            results.append(self.generate_stock_fisico(connector, quants))
        
        # Comprobantes
        if date_from and date_to:
            invoices = self.env['account.move'].search([
                ('move_type', 'in', ['out_invoice', 'out_refund']),
                ('state', '=', 'posted'),
                ('invoice_date', '>=', date_from),
                ('invoice_date', '<=', date_to),
            ])
            if invoices:
                results.append(self.generate_comprobantes(connector, invoices))
        
        return results
    
    # =========================================================================
    # UTILIDADES
    # =========================================================================
    
    def _get_timestamp(self):
        """Genera timestamp para nombre de archivo: AAAAMMDDHHMMSS"""
        return datetime.now().strftime('%Y%m%d%H%M%S')
    
    def _get_filename(self, entity_name, company_code):
        """
        Genera nombre de archivo según especificación.
        Formato: {Entidad}EEEEEEAAAAMMDDHHMMSS.csv
        """
        timestamp = self._get_timestamp()
        # Asegurar que company_code tenga 6 dígitos
        code = str(company_code).zfill(6)
        return f"{entity_name}{code}{timestamp}.csv"
    
    def _format_bool(self, value, format_type='01'):
        """
        Formatea booleano según tipo requerido.
        format_type: '01', 'SINO_upper', 'YESNO_upper', 'sino_lower', 'yesno_lower', 'truefalse'
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
        elif format_type == 'truefalse':
            return 'True' if value else 'False'
        return '1' if value else '0'
    
    def _format_date(self, date_value, format_type='yyyymmdd'):
        """Formatea fecha según tipo requerido."""
        if not date_value:
            return ''
        
        if isinstance(date_value, str):
            return date_value
        
        if format_type == 'yyyymmdd':
            return date_value.strftime(self.DATE_FORMAT_YYYYMMDD)
        elif format_type == 'ddmmyyyy':
            return date_value.strftime(self.DATE_FORMAT_DDMMYYYY)
        return date_value.strftime(self.DATE_FORMAT_YYYYMMDD)
    
    def _format_decimal(self, value, decimals=6):
        """Formatea número decimal."""
        if value is None:
            return '0'
        return str(round(float(value), decimals))
    
    def _format_integer(self, value):
        """Formatea número entero."""
        if value is None:
            return '0'
        return str(int(value))
    
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
        Según documentación: separador ; y primera fila con nombres de campos.
        """
        output = io.StringIO()
        writer = csv.writer(
            output,
            delimiter=self.SEPARATOR,
            quotechar='"',
            quoting=csv.QUOTE_MINIMAL
        )
        
        # Primera fila: headers (según documentación)
        writer.writerow(headers)
        
        # Filas de datos
        for row in rows:
            writer.writerow(row)
        
        return output.getvalue()
    
    # =========================================================================
    # GENERADORES DE ARCHIVOS - SEGÚN DOCUMENTACIÓN OFICIAL
    # =========================================================================
    
    def generate_articulos(self, connector, products):
        """
        Genera Articulos CSV según documentación Nextbyn.
        
        Campos obligatorios:
        - CodigoArticulo (Numérico)
        - DescripcionArticulo (Texto 50)
        - Anulado (Bool)
        - UnidadesXBulto (Numérico)
        
        Campos opcionales importantes:
        - ValorUMedida, UnidadMedida, CodigoEANBulto, CodigoEANUnidad, etc.
        """
        headers = [
            'CodigoArticulo',
            'DescripcionArticulo',
            'Anulado',
            'UnidadesXBulto',
            'ValorUMedida',
            'UnidadMedida',
            'CodigoEANBulto',
            'CodigoEANUnidad',
            'Retornable',
            'ActivoFijo',
        ]
        
        rows = []
        for product in products:
            row = [
                self._format_integer(product.id),  # CodigoArticulo
                self._clean_text(product.name, 50),  # DescripcionArticulo
                self._format_bool(not product.active, 'SINO_upper'),  # Anulado (NO/SI)
                self._format_integer(product.x_softys_unidades_bulto or 1),  # UnidadesXBulto
                self._format_decimal(product.x_softys_valor_umedida or 0, 4),  # ValorUMedida
                self._clean_text(product.uom_id.name if product.uom_id else 'UN', 50),  # UnidadMedida
                self._clean_text(product.barcode or '', 50),  # CodigoEANBulto
                self._clean_text(product.x_softys_ean_unidad or '', 50),  # CodigoEANUnidad
                self._format_bool(product.x_softys_retornable or False, '01'),  # Retornable
                self._format_bool(product.x_softys_activo_fijo or False, '01'),  # ActivoFijo
            ]
            rows.append(row)
        
        filename = self._get_filename('Articulos', connector.company_code)
        content = self._create_csv_content(headers, rows)
        
        return filename, content, len(rows)
    
    def generate_clientes(self, connector, partners):
        """
        Genera Clientes CSV según documentación Nextbyn.
        
        Campos clave únicos: CodigoSucursal, CodigoCliente
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
            'LongitudCoord',
            'LatitudCoord',
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
            # Obtener canal/subcanal
            canal_id = partner.x_softys_canal_id
            subcanal_id = partner.x_softys_subcanal_id
            
            row = [
                self._format_integer(connector.codigo_sucursal or 1),  # CodigoSucursal
                self._clean_text(partner.id, 50),  # CodigoCliente
                self._clean_text(partner.name, 100),  # Nombre
                self._clean_text(self._get_full_address(partner), 100),  # Domicilio
                self._clean_text(partner.vat or '', 50),  # NumeroCuit
                self._format_integer(canal_id.id if canal_id else 0),  # IdCanalAgrupa
                self._clean_text(canal_id.nombre if canal_id else '', 100),  # DescCanalAgrupa
                self._format_integer(subcanal_id.id if subcanal_id else 0),  # IdSubCanalAgrupa
                self._clean_text(subcanal_id.nombre if subcanal_id else '', 100),  # DescSubCanalAgrupa
                self._format_date(partner.create_date, 'ddmmyyyy'),  # FechaAlta
                self._format_bool(not partner.active, 'sino_lower'),  # Anulado (no/si)
                self._format_decimal(partner.partner_longitude or 0, 10),  # LongitudCoord
                self._format_decimal(partner.partner_latitude or 0, 10),  # LatitudCoord
                self._get_tipo_contribuyente(partner),  # TipoContribuyente
                self._format_integer(partner.property_product_pricelist.id if partner.property_product_pricelist else 1),  # CodListaPrecio
                self._get_tipo_documento(partner),  # IdTipoDocumentoCliente
                self._clean_text(partner.zip or '', 20),  # CodigoLocalidad
                self._clean_text(partner.city or '', 100),  # DescripcionLocalidad
                self._clean_text(partner.state_id.code if partner.state_id else '', 50),  # CodigoProvincia
                self._clean_text(partner.state_id.name if partner.state_id else '', 50),  # DescProvincia
            ]
            rows.append(row)
        
        filename = self._get_filename('Clientes', connector.company_code)
        content = self._create_csv_content(headers, rows)
        
        return filename, content, len(rows)
    
    def generate_personal_comercial(self, connector):
        """
        Genera PersonalComercial CSV según documentación Nextbyn.
        
        Campos clave únicos: CodigoPersonal
        Cargos: V=Vendedor, S=Supervisor, G=Gerente, F=Fletero/Repartidor
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
        for personal in connector.personal_comercial_ids:
            row = [
                self._format_integer(connector.codigo_sucursal or 1),  # CodigoSucursal
                self._format_integer(personal.codigo_personal),  # CodigoPersonal
                self._clean_text(personal.descripcion, 50),  # Descripcion
                personal.cargo or 'V',  # Cargo (V/S/G/F)
                self._format_bool(personal.anulado == '1', '01'),  # Anulado (0/1)
                self._format_integer(personal.codigo_personal_superior or 0),  # CodigoPersonalSuperior
                self._format_integer(personal.codigo_fuerza or connector.codigo_fuerza or 1),  # CodigoFuerza
            ]
            rows.append(row)
        
        filename = self._get_filename('PersonalComercial', connector.company_code)
        content = self._create_csv_content(headers, rows)
        
        return filename, content, len(rows)
    
    def generate_rutas_de_venta(self, connector):
        """
        Genera RutasDeVenta CSV según documentación Nextbyn.
        
        Campos clave únicos: CodigoSucursal, CodigoFuerza, CodigoModoAtencion, 
                            CodigoRuta, FechaDesde
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
                ruta.fecha_desde or '2001/01/01',  # FechaDesde (constante si no hay historia)
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
        Genera ClientesRuta CSV según documentación Nextbyn.
        
        Campos clave únicos: CodigoSucursal, CodigoFuerza, CodigoModoAtencion,
                            CodigoRuta, CodigoCliente, FechaDesde
        """
        headers = [
            'CodigoSucursal',
            'CodigoFuerza',
            'CodigoModoAtencion',
            'CodigoRuta',
            'CodigoCliente',
            'FechaDesde',
            'FechaHasta',
            'Periodicidad',
            'Semana',
            'VisitaLunes',
            'VisitaMartes',
            'VisitaMiercoles',
            'VisitaJueves',
            'VisitaViernes',
            'VisitaSabado',
            'VisitaDomingo',
            'OrdenDeVisita',
        ]
        
        rows = []
        for partner in partners:
            if not partner.x_softys_codigo_ruta:
                continue
            
            row = [
                self._format_integer(connector.codigo_sucursal or 1),  # CodigoSucursal
                self._format_integer(connector.codigo_fuerza or 1),  # CodigoFuerza
                self._clean_text(connector.codigo_modo_atencion or 'PRE', 5),  # CodigoModoAtencion
                self._format_integer(partner.x_softys_codigo_ruta or 0),  # CodigoRuta
                self._clean_text(partner.id, 50),  # CodigoCliente
                '2001/01/01',  # FechaDesde (constante si no hay historia)
                '9999/12/31',  # FechaHasta (máxima si está activo)
                self._format_integer(1),  # Periodicidad
                self._format_integer(1),  # Semana
                self._format_bool(partner.x_softys_dia_visita == 'LUN', '01'),  # VisitaLunes
                self._format_bool(partner.x_softys_dia_visita == 'MAR', '01'),  # VisitaMartes
                self._format_bool(partner.x_softys_dia_visita == 'MIE', '01'),  # VisitaMiercoles
                self._format_bool(partner.x_softys_dia_visita == 'JUE', '01'),  # VisitaJueves
                self._format_bool(partner.x_softys_dia_visita == 'VIE', '01'),  # VisitaViernes
                self._format_bool(partner.x_softys_dia_visita == 'SAB', '01'),  # VisitaSabado
                self._format_bool(partner.x_softys_dia_visita == 'DOM', '01'),  # VisitaDomingo
                self._format_integer(partner.x_softys_secuencia or 0),  # OrdenDeVisita
            ]
            rows.append(row)
        
        filename = self._get_filename('ClientesRuta', connector.company_code)
        content = self._create_csv_content(headers, rows)
        
        return filename, content, len(rows)
    
    def generate_stock_fisico(self, connector, stock_quants):
        """
        Genera StockFisico CSV según documentación Nextbyn.
        
        Campos clave únicos: CodigoDeposito, CodigoArticulo, FechaStock, VencimientoLote
        """
        headers = [
            'CodigoDeposito',
            'CodigoArticulo',
            'VencimientoLote',
            'CantidadDecimal',
            'FechaStock',
        ]
        
        rows = []
        today = fields.Date.today()
        
        for quant in stock_quants:
            # Obtener código de depósito
            warehouse = quant.location_id.warehouse_id
            deposito_code = warehouse.x_softys_codigo_deposito if warehouse else connector.codigo_deposito or '1'
            
            # Fecha de vencimiento del lote (si existe)
            lot = quant.lot_id
            vencimiento = lot.expiration_date if lot and lot.expiration_date else today
            
            row = [
                self._format_integer(deposito_code),  # CodigoDeposito
                self._format_integer(quant.product_id.id),  # CodigoArticulo
                self._format_date(vencimiento, 'yyyymmdd'),  # VencimientoLote
                self._format_decimal(quant.quantity, 6),  # CantidadDecimal
                self._format_date(today, 'yyyymmdd'),  # FechaStock
            ]
            rows.append(row)
        
        filename = self._get_filename('StockFisico', connector.company_code)
        content = self._create_csv_content(headers, rows)
        
        return filename, content, len(rows)
    
    def generate_comprobantes(self, connector, invoices):
        """
        Genera Comprobantes CSV según documentación Nextbyn.
        
        Campos clave únicos: CodigoEmpresaFactura, TipoComprobante, LetraComprobante,
                            SerieComprobante, NumeroComprobante, NumeroLinea
        """
        headers = [
            'CodigoEmpresaFactura',
            'TipoComprobante',
            'LetraComprobante',
            'SerieComprobante',
            'NumeroComprobante',
            'NumeroLinea',
            'CodigoTalonario',
            'CodigoFuerza',
            'EsVenta',
            'EsEntrega',
            'CodigoArticulo',
            'DescripcionArticulo',
            'UnidadesPorBulto',
            'CantidadDecimal',
            'PrecioUnitarioBruto',
            'Bonificacion',
            'FechaPedido',
            'CodigoPersonal',
            'FechaComprobante',
            'HoraFactura',
            'CodigoCliente',
            'CodigoSucursal',
            'NombreCliente',
            'TipoContribuyente',
            'Anulado',
        ]
        
        rows = []
        
        for invoice in invoices:
            # Parsear número de factura argentina
            tipo, letra, serie, numero = self._parse_invoice_number(invoice)
            
            line_num = 0
            for line in invoice.invoice_line_ids.filtered(lambda l: l.product_id):
                line_num += 1
                
                # Determinar si es venta (facturas) o no (NC)
                es_venta = invoice.move_type in ('out_invoice', 'out_refund')
                
                # Cantidad: positiva para facturas, negativa para NC
                cantidad = line.quantity
                if invoice.move_type == 'out_refund':
                    cantidad = -abs(cantidad)
                
                row = [
                    self._format_integer(connector.company_code),  # CodigoEmpresaFactura
                    self._clean_text(tipo, 6),  # TipoComprobante
                    self._clean_text(letra, 10),  # LetraComprobante
                    self._format_integer(serie),  # SerieComprobante
                    self._format_integer(numero),  # NumeroComprobante
                    self._format_integer(line_num),  # NumeroLinea
                    self._format_integer(0),  # CodigoTalonario
                    self._format_integer(connector.codigo_fuerza or 1),  # CodigoFuerza
                    self._format_bool(es_venta, 'YESNO_upper'),  # EsVenta (YES/NO)
                    self._format_bool(es_venta, 'YESNO_upper'),  # EsEntrega (YES/NO)
                    self._format_integer(line.product_id.id),  # CodigoArticulo
                    self._clean_text(line.product_id.name, 50),  # DescripcionArticulo
                    self._format_integer(line.product_id.x_softys_unidades_bulto or 1),  # UnidadesPorBulto
                    self._format_decimal(cantidad, 6),  # CantidadDecimal
                    self._format_decimal(line.price_unit, 6),  # PrecioUnitarioBruto
                    self._format_decimal(line.discount or 0, 3),  # Bonificacion
                    self._format_date(invoice.invoice_date, 'ddmmyyyy'),  # FechaPedido
                    self._format_integer(self._get_vendedor_code(invoice, connector)),  # CodigoPersonal
                    self._format_date(invoice.invoice_date, 'ddmmyyyy'),  # FechaComprobante
                    self._format_time(invoice.create_date),  # HoraFactura
                    self._clean_text(invoice.partner_id.id, 50),  # CodigoCliente
                    self._format_integer(connector.codigo_sucursal or 1),  # CodigoSucursal
                    self._clean_text(invoice.partner_id.name, 100),  # NombreCliente
                    self._get_tipo_contribuyente(invoice.partner_id),  # TipoContribuyente
                    self._format_bool(invoice.state == 'cancel', 'SINO_upper'),  # Anulado (NO/SI)
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
        Obtiene código de tipo contribuyente.
        Según documentación: texto de 2 caracteres.
        """
        # Mapeo de l10n_ar a códigos Nextbyn
        afip_type = partner.l10n_ar_afip_responsibility_type_id
        if afip_type:
            code = afip_type.code
            mapping = {
                '1': 'RI',   # Responsable Inscripto
                '4': 'EX',   # Exento
                '5': 'CF',   # Consumidor Final
                '6': 'MT',   # Monotributista
                '9': 'EX',   # Exento
            }
            return mapping.get(code, 'CF')
        return 'CF'  # Default: Consumidor Final
    
    def _get_tipo_documento(self, partner):
        """
        Obtiene código de tipo de documento.
        80 = CUIT, 96 = DNI, etc.
        """
        doc_type = partner.l10n_latam_identification_type_id
        if doc_type:
            if 'cuit' in doc_type.name.lower():
                return '80'
            elif 'dni' in doc_type.name.lower():
                return '96'
        return '96'  # Default: DNI
    
    def _parse_invoice_number(self, invoice):
        """
        Parsea número de factura argentina.
        Formato esperado: FA-A 0001-00000001
        Retorna: (tipo, letra, serie, numero)
        """
        name = invoice.name or ''
        
        # Valores por defecto
        tipo = 'FCVTA'
        letra = 'A'
        serie = 1
        numero = 0
        
        # Intentar parsear formato argentino
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
        
        # Parsear número
        if name:
            parts = name.replace('-', ' ').split()
            for part in parts:
                if part.isdigit():
                    if len(part) <= 5:
                        serie = int(part)
                    else:
                        numero = int(part)
        
        return tipo, letra, serie, numero
    
    def _format_time(self, datetime_value):
        """Formatea hora."""
        if not datetime_value:
            return '00:00:00'
        return datetime_value.strftime(self.TIME_FORMAT)
    
    def _get_vendedor_code(self, invoice, connector):
        """Obtiene código de vendedor para factura."""
        if invoice.x_softys_vendedor_id:
            return invoice.x_softys_vendedor_id.x_softys_codigo or 0
        
        # Usar primer personal comercial como default
        if connector.personal_comercial_ids:
            return connector.personal_comercial_ids[0].codigo_personal
        
        return 0
