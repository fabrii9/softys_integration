# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging
import os
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class SoftysConnector(models.Model):
    """
    Configuración principal de la integración con Softys.
    Equivalente a los parámetros hardcodeados en la transformación Pentaho.
    """
    _name = 'softys.connector'
    _description = 'Configuración Integración Softys'
    _rec_name = 'company_code'
    
    # Configuración básica
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
        help='Compañía de Odoo que corresponde a empresa=4 en YAS'
    )
    
    company_code = fields.Char(
        string='Código Empresa Softys',
        required=True,
        default='001971',
        help='Código de empresa en sistema Softys (ej: 001971)'
    )
    
    active = fields.Boolean(
        string='Activo',
        default=True
    )
    
    # Configuración de rutas y archivos
    output_path = fields.Char(
        string='Carpeta Salida',
        required=True,
        default='/tmp/softys/output',
        help='Ruta donde se generarán los archivos CSV. '
             'Equivalente a E:\\Proyectos\\Softys\\Output\\'
    )
    
    output_storage_type = fields.Selection([
        ('filesystem', 'Sistema de Archivos'),
        ('attachment', 'Adjuntos Odoo'),
        ('both', 'Ambos'),
    ], string='Tipo Almacenamiento', required=True, default='both',
       help='Dónde guardar los archivos generados')
    
    # Configuración de filtros
    days_back = fields.Integer(
        string='Días hacia atrás (Comprobantes)',
        required=True,
        default=98,
        help='Cantidad de días para filtrar comprobantes. '
             'SQL: f.fecha >= CURDATE() - INTERVAL 98 DAY'
    )
    
    # Configuración de códigos fijos
    codigo_sucursal = fields.Char(
        string='Código Sucursal',
        required=True,
        default='1',
        help='Código de sucursal fijo en exports'
    )
    
    codigo_fuerza = fields.Char(
        string='Código Fuerza',
        required=True,
        default='1',
        help='Código de fuerza de ventas'
    )
    
    codigo_modo_atencion = fields.Char(
        string='Código Modo Atención',
        required=True,
        default='PRE',
        help='Modo de atención (PRE=Preventa)'
    )
    
    codigo_ruta_default = fields.Char(
        string='Código Ruta por Defecto',
        required=True,
        default='00',
        help='Código de ruta cuando no se especifica'
    )
    
    desc_ruta_default = fields.Char(
        string='Descripción Ruta por Defecto',
        required=True,
        default='SIN ZONA',
        help='Descripción de ruta por defecto'
    )
    
    codigo_deposito = fields.Char(
        string='Código Depósito',
        required=True,
        default='1',
        help='Código de depósito para Stock Físico'
    )
    
    # Configuración de provincia por defecto (Misiones)
    provincia_codigo_default = fields.Char(
        string='Código Provincia Default',
        default='19',
        help='Código de provincia por defecto (19=Misiones)'
    )
    
    provincia_nombre_default = fields.Char(
        string='Nombre Provincia Default',
        default='MISIONES',
        help='Nombre de provincia por defecto'
    )
    
    localidad_default = fields.Char(
        string='Localidad por Defecto',
        default='PUERTO IGUAZU - 3370',
        help='Localidad cuando zona es null o "Sin Zona"'
    )
    
    # Configuración de fechas extremas
    fecha_desde_default = fields.Char(
        string='Fecha Desde Default',
        default='1900/01/01',
        help='Fecha inicio por defecto para rutas'
    )
    
    fecha_hasta_default = fields.Char(
        string='Fecha Hasta Default',
        default='9999/12/31',
        help='Fecha fin por defecto (máxima)'
    )
    
    # Configuración de encoding
    csv_encoding = fields.Selection([
        ('utf-8', 'UTF-8'),
        ('windows-1252', 'Windows-1252 (ANSI)'),
        ('windows-1250', 'Windows-1250 (Central European)'),
        ('iso-8859-1', 'ISO-8859-1 (Latin-1)'),
    ], string='Encoding CSV', required=True, default='utf-8',
       help='Encoding para archivos CSV. '
            'NO ESPECIFICADO en .ktr - confirmar con Softys')
    
    csv_separator = fields.Char(
        string='Separador CSV',
        required=True,
        default=';',
        size=1,
        help='Separador de campos (punto y coma)'
    )
    
    csv_enclosure = fields.Char(
        string='Comillas CSV',
        default='"',
        size=1,
        help='Carácter de enclosure (comillas dobles). '
             'Dejar vacío para sin comillas'
    )
    
    # Configuración de personal comercial
    personal_comercial_ids = fields.One2many(
        'softys.personal.comercial',
        'connector_id',
        string='Personal Comercial'
    )
    
    # Configuración de rutas de venta
    ruta_venta_ids = fields.One2many(
        'softys.ruta.venta',
        'connector_id',
        string='Rutas de Venta'
    )
    
    # Estadísticas
    last_export_date = fields.Datetime(
        string='Última Exportación',
        readonly=True
    )
    
    last_export_status = fields.Selection([
        ('success', 'Éxito'),
        ('partial', 'Parcial'),
        ('failed', 'Fallido'),
    ], string='Estado Última Exportación', readonly=True)
    
    export_count = fields.Integer(
        string='Total Exportaciones',
        compute='_compute_export_count'
    )
    
    # Proveedor Softys
    softys_partner_id = fields.Many2one(
        'res.partner',
        string='Proveedor Softys',
        domain=[('supplier_rank', '>', 0)],
        help='Partner que representa a Softys (IdCliente=1533 en YAS). '
             'Los productos con este proveedor se exportan.'
    )
    
    @api.depends('company_id')
    def _compute_export_count(self):
        for record in self:
            record.export_count = self.env['softys.export.run'].search_count([
                ('connector_id', '=', record.id)
            ])
    
    @api.constrains('company_code')
    def _check_company_code(self):
        for record in self:
            if not record.company_code or len(record.company_code) != 6:
                raise ValidationError(
                    _('El código de empresa debe tener exactamente 6 dígitos.')
                )
    
    @api.constrains('csv_separator', 'csv_enclosure')
    def _check_csv_chars(self):
        for record in self:
            if record.csv_separator and len(record.csv_separator) > 1:
                raise ValidationError(_('El separador debe ser un solo carácter.'))
            if record.csv_enclosure and len(record.csv_enclosure) > 1:
                raise ValidationError(_('El enclosure debe ser un solo carácter.'))
    
    def action_view_exports(self):
        """Ver historial de exportaciones"""
        self.ensure_one()
        return {
            'name': _('Exportaciones Softys'),
            'type': 'ir.actions.act_window',
            'res_model': 'softys.export.run',
            'view_mode': 'tree,form',
            'domain': [('connector_id', '=', self.id)],
            'context': {'default_connector_id': self.id}
        }
    
    def action_export_manual(self):
        """Ejecutar exportación manual"""
        self.ensure_one()
        return {
            'name': _('Exportar a Softys'),
            'type': 'ir.actions.act_window',
            'res_model': 'softys.export.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_connector_id': self.id}
        }
    
    def cron_export_softys(self):
        """
        Método llamado por cron para exportación automática.
        Exporta todos los conectores activos.
        """
        connectors = self.search([('active', '=', True)])
        for connector in connectors:
            try:
                _logger.info(f'Iniciando exportación automática Softys para {connector.company_code}')
                wizard = self.env['softys.export.wizard'].create({
                    'connector_id': connector.id,
                })
                wizard.action_export()
                _logger.info(f'Exportación automática completada para {connector.company_code}')
            except Exception as e:
                _logger.error(f'Error en exportación automática Softys {connector.company_code}: {str(e)}')
                # No detener el cron si falla una empresa
                continue
    
    def _create_output_directory(self):
        """Crear carpeta de salida si no existe"""
        self.ensure_one()
        if self.output_storage_type in ('filesystem', 'both'):
            if not os.path.exists(self.output_path):
                try:
                    os.makedirs(self.output_path, exist_ok=True)
                    _logger.info(f'Directorio creado: {self.output_path}')
                except Exception as e:
                    raise UserError(
                        _('No se pudo crear el directorio de salida: %s\nError: %s')
                        % (self.output_path, str(e))
                    )


class SoftysPersonalComercial(models.Model):
    """
    Personal Comercial para exportar (reemplaza RowGenerator hardcodeado).
    En la transformación original era completamente fijo: Alejandro Ayala.
    """
    _name = 'softys.personal.comercial'
    _description = 'Personal Comercial Softys'
    _order = 'sequence, codigo_personal'
    
    connector_id = fields.Many2one(
        'softys.connector',
        string='Conector',
        required=True,
        ondelete='cascade'
    )
    
    sequence = fields.Integer(string='Secuencia', default=10)
    
    employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado',
        help='Empleado de Odoo (opcional)'
    )
    
    codigo_personal = fields.Char(
        string='Código Personal',
        required=True,
        help='Código en sistema Softys'
    )
    
    descripcion = fields.Char(
        string='Descripción',
        required=True,
        help='Nombre completo del vendedor'
    )
    
    cargo = fields.Selection([
        ('V', 'Vendedor'),
        ('S', 'Supervisor'),
        ('G', 'Gerente'),
        ('F', 'Repartidor/Fletero'),
    ], string='Cargo', required=True, default='V',
       help='V=Vendedor, S=Supervisor, G=Gerente, F=Repartidor/Fletero')
    
    anulado = fields.Selection([
        ('0', 'Activo'),
        ('1', 'Anulado'),
    ], string='Estado', required=True, default='0')
    
    codigo_personal_superior = fields.Char(
        string='Código Superior',
        help='Código del supervisor/jefe directo. Dejar en blanco si no tiene.'
    )
    
    codigo_fuerza = fields.Char(
        string='Código Fuerza',
        help='Código de fuerza de ventas. Si vacío, usa el del conector.'
    )
    
    active = fields.Boolean(string='Activo', default=True)


class SoftysRutaVenta(models.Model):
    """
    Rutas de Venta para exportar según documentación Nextbyn.
    
    Campos clave únicos: CodigoSucursal, CodigoFuerza, CodigoModoAtencion,
                        CodigoRuta, FechaDesde
    """
    _name = 'softys.ruta.venta'
    _description = 'Ruta de Venta Nextbyn'
    _order = 'codigo_ruta'
    
    connector_id = fields.Many2one(
        'softys.connector',
        string='Conector',
        required=True,
        ondelete='cascade'
    )
    
    codigo_ruta = fields.Char(
        string='Código Ruta',
        required=True,
        help='Código de ruta en Nextbyn'
    )
    
    descripcion_ruta = fields.Char(
        string='Descripción',
        required=True,
        help='Nombre de la ruta'
    )
    
    codigo_personal = fields.Char(
        string='Código Personal',
        required=True,
        help='Código del vendedor asignado a la ruta'
    )
    
    fecha_desde = fields.Char(
        string='Fecha Desde',
        default='2001/01/01',
        help='Formato yyyy/MM/dd. Constante 2001/01/01 si no se conserva historia.'
    )
    
    # Campos adicionales según documentación Nextbyn
    periodicidad = fields.Integer(
        string='Periodicidad',
        default=1,
        help='Periodicidad de la visita'
    )
    
    semana = fields.Integer(
        string='Semana',
        default=1,
        help='Semana de visita'
    )
    
    # Días de atención
    atiende_lunes = fields.Boolean(
        string='Lunes',
        default=False,
        help='Si la ruta se hace los días Lunes'
    )
    
    atiende_martes = fields.Boolean(
        string='Martes',
        default=False,
        help='Si la ruta se hace los días Martes'
    )
    
    atiende_miercoles = fields.Boolean(
        string='Miércoles',
        default=False,
        help='Si la ruta se hace los días Miércoles'
    )
    
    atiende_jueves = fields.Boolean(
        string='Jueves',
        default=False,
        help='Si la ruta se hace los días Jueves'
    )
    
    atiende_viernes = fields.Boolean(
        string='Viernes',
        default=False,
        help='Si la ruta se hace los días Viernes'
    )
    
    atiende_sabado = fields.Boolean(
        string='Sábado',
        default=False,
        help='Si la ruta se hace los días Sábado'
    )
    
    atiende_domingo = fields.Boolean(
        string='Domingo',
        default=False,
        help='Si la ruta se hace los días Domingo'
    )
    
    active = fields.Boolean(string='Activo', default=True)
