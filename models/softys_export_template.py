# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SoftysExportTemplate(models.Model):
    """
    Define los 7 templates de archivos CSV a generar.
    Cada template corresponde a un TextFileOutput del .ktr
    """
    _name = 'softys.export.template'
    _description = 'Template de Exportación Softys'
    _order = 'sequence, name'
    
    name = fields.Char(
        string='Nombre',
        required=True,
        help='Nombre del archivo sin extensión'
    )
    
    sequence = fields.Integer(
        string='Secuencia',
        default=10,
        help='Orden de generación'
    )
    
    active = fields.Boolean(
        string='Activo',
        default=True,
        help='Si está inactivo, no se genera este archivo'
    )
    
    file_type = fields.Selection([
        ('clientes', 'Clientes'),
        ('articulos', 'Artículos'),
        ('comprobantes', 'Comprobantes'),
        ('personal_comercial', 'Personal Comercial'),
        ('clientes_ruta', 'Clientes Ruta'),
        ('rutas_venta', 'Rutas de Venta'),
        ('stock_fisico', 'Stock Físico'),
    ], string='Tipo Archivo', required=True)
    
    description = fields.Text(
        string='Descripción',
        help='Descripción del archivo y su contenido'
    )
    
    # Configuración de formato
    encoding = fields.Selection([
        ('utf-8', 'UTF-8'),
        ('windows-1252', 'Windows-1252 (ANSI)'),
        ('windows-1250', 'Windows-1250 (Central European)'),
        ('iso-8859-1', 'ISO-8859-1 (Latin-1)'),
    ], string='Encoding', 
       help='Encoding específico para este archivo. Si vacío, usa el del conector.')
    
    separator = fields.Char(
        string='Separador',
        size=1,
        help='Separador de campos. Si vacío, usa el del conector.'
    )
    
    enclosure = fields.Char(
        string='Comillas',
        size=1,
        help='Carácter de enclosure. Si vacío, usa el del conector.'
    )
    
    header = fields.Boolean(
        string='Incluir Header',
        default=False,
        help='Si debe incluir línea de encabezados con nombres de columnas'
    )
    
    # Definición de columnas
    column_ids = fields.One2many(
        'softys.export.column',
        'template_id',
        string='Columnas',
        copy=True
    )
    
    column_count = fields.Integer(
        string='Total Columnas',
        compute='_compute_column_count',
        store=True
    )
    
    @api.depends('column_ids')
    def _compute_column_count(self):
        for record in self:
            record.column_count = len(record.column_ids)
    
    @api.constrains('file_type')
    def _check_unique_file_type(self):
        for record in self:
            if record.active:
                duplicates = self.search([
                    ('file_type', '=', record.file_type),
                    ('active', '=', True),
                    ('id', '!=', record.id)
                ])
                if duplicates:
                    raise ValidationError(
                        _('Ya existe un template activo para el tipo %s') % 
                        dict(self._fields['file_type'].selection)[record.file_type]
                    )
    
    def _get_column_schema(self):
        """
        Retorna el schema de columnas ordenado por secuencia.
        Formato: [(nombre, tipo, formato, precision, aplicar_mapping), ...]
        """
        self.ensure_one()
        return [(
            col.name,
            col.data_type,
            col.format_string,
            col.precision,
            col.length,
            col.apply_mapping,
            col.null_string,
            col.trim_type
        ) for col in self.column_ids.sorted('sequence')]


class SoftysExportColumn(models.Model):
    """
    Define cada columna de un template de exportación.
    Equivalente a los fields en TextFileOutput del .ktr
    """
    _name = 'softys.export.column'
    _description = 'Columna de Exportación Softys'
    _order = 'template_id, sequence, name'
    
    template_id = fields.Many2one(
        'softys.export.template',
        string='Template',
        required=True,
        ondelete='cascade'
    )
    
    sequence = fields.Integer(
        string='Secuencia',
        required=True,
        default=10,
        help='Orden de la columna en el archivo'
    )
    
    name = fields.Char(
        string='Nombre Campo',
        required=True,
        help='Nombre de la columna en el CSV'
    )
    
    data_type = fields.Selection([
        ('String', 'String'),
        ('Number', 'Number'),
        ('Integer', 'Integer'),
        ('BigNumber', 'BigNumber'),
        ('Date', 'Date'),
        ('Boolean', 'Boolean'),
    ], string='Tipo Dato', required=True, default='String')
    
    format_string = fields.Char(
        string='Formato',
        help='Formato de salida (ej: yyyy/MM/dd para fechas, #.# para números)'
    )
    
    precision = fields.Integer(
        string='Precisión',
        help='Precisión para números (cantidad de decimales)'
    )
    
    length = fields.Integer(
        string='Longitud',
        default=-1,
        help='Longitud máxima del campo. -1 = sin límite'
    )
    
    null_string = fields.Char(
        string='Valor si NULL',
        help='Valor a usar cuando el campo es NULL/vacío'
    )
    
    trim_type = fields.Selection([
        ('none', 'Ninguno'),
        ('left', 'Izquierda'),
        ('right', 'Derecha'),
        ('both', 'Ambos'),
    ], string='Trim', default='none',
       help='Eliminar espacios en blanco')
    
    apply_mapping = fields.Boolean(
        string='Aplicar Mapping',
        default=False,
        help='Si debe aplicar transformaciones de ValueMapper/Rules'
    )
    
    # Campos técnicos para referencia
    odoo_field = fields.Char(
        string='Campo Odoo',
        help='Campo de Odoo desde donde se obtiene el valor (referencia)'
    )
    
    notes = fields.Text(
        string='Notas',
        help='Notas técnicas sobre esta columna'
    )
    
    @api.constrains('precision')
    def _check_precision(self):
        for record in self:
            if record.precision < 0:
                raise ValidationError(_('La precisión debe ser mayor o igual a 0'))
