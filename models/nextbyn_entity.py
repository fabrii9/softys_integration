# -*- coding: utf-8 -*-
"""
Entidades de exportación Nextbyn - Configuración dinámica de CSVs.
Permite configurar desde la interfaz de Odoo qué campos exportar y cómo mapearlos.
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class NextbynExportEntity(models.Model):
    """
    Representa una entidad/archivo CSV de Nextbyn.
    Ej: Articulos, Clientes, Comprobantes, etc.
    """
    _name = 'nextbyn.export.entity'
    _description = 'Entidad de Exportación Nextbyn'
    _order = 'sequence, name'
    
    name = fields.Char(
        string='Nombre Entidad',
        required=True,
        help='Nombre del archivo CSV (sin extensión). Ej: Articulos, Clientes'
    )
    
    sequence = fields.Integer(
        string='Secuencia',
        default=10,
        help='Orden de exportación'
    )
    
    active = fields.Boolean(
        string='Activo',
        default=True,
        help='Si está activo, se exportará'
    )
    
    model_id = fields.Many2one(
        'ir.model',
        string='Modelo Odoo',
        required=True,
        ondelete='cascade',
        help='Modelo de Odoo del cual se extraen los datos'
    )
    
    model_name = fields.Char(
        string='Nombre Técnico',
        related='model_id.model',
        store=True,
        readonly=True
    )
    
    domain = fields.Text(
        string='Filtro (Dominio)',
        default='[]',
        help='Dominio en formato Python para filtrar registros. Ej: [(\'active\', \'=\', True)]'
    )
    
    connector_id = fields.Many2one(
        'softys.connector',
        string='Conector',
        ondelete='cascade',
        help='Conector Nextbyn asociado'
    )
    
    # Campos de la entidad
    field_ids = fields.One2many(
        'nextbyn.export.field',
        'entity_id',
        string='Campos',
        copy=True
    )
    
    field_count = fields.Integer(
        string='Cantidad Campos',
        compute='_compute_field_count'
    )
    
    # Configuración adicional
    include_header = fields.Boolean(
        string='Incluir Encabezado',
        default=True,
        help='Primera fila con nombres de campos (según documentación Nextbyn: SÍ)'
    )
    
    separator = fields.Selection([
        (';', 'Punto y coma (;)'),
        (',', 'Coma (,)'),
        ('|', 'Pipe (|)'),
        ('\t', 'Tabulador'),
    ], string='Separador',
       default=';',
       required=True,
       help='Según documentación Nextbyn: punto y coma (;)')
    
    encoding = fields.Selection([
        ('utf-8', 'UTF-8'),
        ('latin-1', 'Latin-1 (ISO-8859-1)'),
        ('cp1252', 'Windows-1252'),
    ], string='Codificación',
       default='utf-8',
       required=True)
    
    notes = fields.Text(
        string='Notas',
        help='Notas o documentación sobre esta entidad'
    )
    
    # Estadísticas última exportación
    last_export_date = fields.Datetime(
        string='Última Exportación',
        readonly=True
    )
    
    last_export_count = fields.Integer(
        string='Registros Exportados',
        readonly=True
    )
    
    @api.depends('field_ids')
    def _compute_field_count(self):
        for entity in self:
            entity.field_count = len(entity.field_ids)
    
    @api.constrains('domain')
    def _check_domain(self):
        for entity in self:
            try:
                domain = eval(entity.domain or '[]')
                if not isinstance(domain, list):
                    raise ValidationError(_('El dominio debe ser una lista.'))
            except Exception as e:
                raise ValidationError(_('Dominio inválido: %s') % str(e))
    
    def action_view_fields(self):
        """Abrir vista de campos de esta entidad"""
        self.ensure_one()
        return {
            'name': _('Campos de %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'nextbyn.export.field',
            'view_mode': 'list,form',
            'domain': [('entity_id', '=', self.id)],
            'context': {'default_entity_id': self.id},
        }
    
    def action_preview_data(self):
        """Ver preview de los datos que se exportarían"""
        self.ensure_one()
        # Obtener primeros 10 registros
        domain = eval(self.domain or '[]')
        records = self.env[self.model_name].search(domain, limit=10)
        
        # Generar preview
        preview_lines = []
        fields_sorted = self.field_ids.sorted('sequence')
        
        # Header
        if self.include_header:
            header = self.separator.join(f.nextbyn_name for f in fields_sorted)
            preview_lines.append(header)
        
        # Data rows
        for record in records:
            row_values = []
            for field in fields_sorted:
                value = field._get_value_from_record(record)
                row_values.append(str(value) if value is not None else '')
            preview_lines.append(self.separator.join(row_values))
        
        # Mostrar en wizard
        preview_text = '\n'.join(preview_lines)
        
        return {
            'name': _('Preview: %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'nextbyn.preview.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_entity_id': self.id,
                'default_preview_text': preview_text,
                'default_record_count': len(records),
            },
        }
    
    def action_test_export(self):
        """Ejecutar exportación de prueba"""
        self.ensure_one()
        content, count = self._generate_csv_content()
        
        return {
            'name': _('Resultado Exportación: %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'nextbyn.preview.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_entity_id': self.id,
                'default_preview_text': content[:10000],  # Limitar preview
                'default_record_count': count,
            },
        }
    
    def _generate_csv_content(self):
        """
        Genera el contenido CSV basado en la configuración de campos.
        Retorna (content, record_count)
        """
        self.ensure_one()
        
        # Obtener registros
        domain = eval(self.domain or '[]')
        records = self.env[self.model_name].search(domain)
        
        lines = []
        fields_sorted = self.field_ids.sorted('sequence')
        
        # Header
        if self.include_header:
            header = self.separator.join(f.nextbyn_name for f in fields_sorted)
            lines.append(header)
        
        # Data rows
        for record in records:
            row_values = []
            for field in fields_sorted:
                value = field._get_value_from_record(record)
                formatted = field._format_value(value)
                row_values.append(formatted)
            lines.append(self.separator.join(row_values))
        
        content = '\n'.join(lines)
        
        # Actualizar estadísticas
        self.write({
            'last_export_date': fields.Datetime.now(),
            'last_export_count': len(records),
        })
        
        return content, len(records)
    
    def _get_filename(self, company_code):
        """Genera nombre de archivo con timestamp"""
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        code = str(company_code).zfill(6)
        return f"{self.name}{code}{timestamp}.csv"


class NextbynExportField(models.Model):
    """
    Campo de una entidad de exportación Nextbyn.
    Define el mapeo entre campo Nextbyn y campo/expresión Odoo.
    """
    _name = 'nextbyn.export.field'
    _description = 'Campo de Exportación Nextbyn'
    _order = 'sequence, id'
    
    entity_id = fields.Many2one(
        'nextbyn.export.entity',
        string='Entidad',
        required=True,
        ondelete='cascade'
    )
    
    sequence = fields.Integer(
        string='Secuencia',
        default=10,
        help='Orden del campo en el CSV (columna)'
    )
    
    nextbyn_name = fields.Char(
        string='Campo Nextbyn',
        required=True,
        help='Nombre del campo en el CSV según documentación. Ej: CodigoArticulo'
    )
    
    # Fuente del valor
    source_type = fields.Selection([
        ('field', 'Campo de Odoo'),
        ('related', 'Campo Relacionado'),
        ('expression', 'Expresión Python'),
        ('fixed', 'Valor Fijo'),
        ('sequence', 'Secuencia/Contador'),
    ], string='Tipo de Origen',
       default='field',
       required=True,
       help='De dónde se obtiene el valor')
    
    # Campo de Odoo (cuando source_type = 'field')
    field_id = fields.Many2one(
        'ir.model.fields',
        string='Campo Odoo',
        help='Campo del modelo a exportar'
    )
    
    field_name = fields.Char(
        string='Nombre Técnico Campo',
        compute='_compute_field_name',
        store=True,
        readonly=True
    )
    
    @api.depends('field_id')
    def _compute_field_name(self):
        for record in self:
            record.field_name = record.field_id.name if record.field_id else False
    
    # Campo relacionado (cuando source_type = 'related')
    related_field_path = fields.Char(
        string='Ruta Campo Relacionado',
        help='Ruta al campo relacionado. Ej: partner_id.name, state_id.code'
    )
    
    # Expresión Python (cuando source_type = 'expression')
    python_expression = fields.Text(
        string='Expresión Python',
        help='Expresión Python. Variables disponibles: record, env, datetime, date. Ej: record.name.upper()'
    )
    
    # Valor fijo (cuando source_type = 'fixed')
    fixed_value = fields.Char(
        string='Valor Fijo',
        help='Valor constante a exportar'
    )
    
    # Tipo de dato y formato
    data_type = fields.Selection([
        ('string', 'Texto'),
        ('integer', 'Entero'),
        ('float', 'Decimal'),
        ('boolean', 'Booleano'),
        ('date', 'Fecha'),
        ('datetime', 'Fecha y Hora'),
        ('time', 'Hora'),
    ], string='Tipo de Dato',
       default='string',
       required=True)
    
    # Formato para booleanos
    bool_format = fields.Selection([
        ('01', '0 / 1'),
        ('SINO_upper', 'NO / SI (mayúsculas)'),
        ('YESNO_upper', 'NO / YES (mayúsculas)'),
        ('sino_lower', 'no / si (minúsculas)'),
        ('yesno_lower', 'no / yes (minúsculas)'),
        ('truefalse', 'False / True'),
    ], string='Formato Booleano',
       default='01',
       help='Formato para valores booleanos. Primer valor = False, segundo = True')
    
    # Formato para fechas
    date_format = fields.Selection([
        ('yyyy/MM/dd', 'yyyy/MM/dd (2026/02/04)'),
        ('dd/MM/yyyy', 'dd/MM/yyyy (04/02/2026)'),
        ('yyyy-MM-dd', 'yyyy-MM-dd (2026-02-04)'),
        ('dd-MM-yyyy', 'dd-MM-yyyy (04-02-2026)'),
        ('yyyyMMdd', 'yyyyMMdd (20260204)'),
    ], string='Formato Fecha',
       default='yyyy/MM/dd',
       help='Formato para campos de fecha')
    
    time_format = fields.Selection([
        ('HH:MM:SS', 'HH:MM:SS (14:30:00)'),
        ('HH:MM', 'HH:MM (14:30)'),
        ('HHMMSS', 'HHMMSS (143000)'),
    ], string='Formato Hora',
       default='HH:MM:SS')
    
    # Formato para decimales
    decimal_places = fields.Integer(
        string='Decimales',
        default=2,
        help='Cantidad de decimales para números'
    )
    
    decimal_separator = fields.Selection([
        ('.', 'Punto (.)'),
        (',', 'Coma (,)'),
    ], string='Separador Decimal',
       default='.',
       help='Separador de decimales')
    
    # Restricciones
    max_length = fields.Integer(
        string='Longitud Máxima',
        help='Longitud máxima del texto (0 = sin límite)'
    )
    
    required = fields.Boolean(
        string='Obligatorio',
        default=False,
        help='Si el campo es obligatorio según documentación'
    )
    
    default_value = fields.Char(
        string='Valor por Defecto',
        help='Valor a usar si el campo está vacío'
    )
    
    # Transformaciones
    trim_spaces = fields.Boolean(
        string='Eliminar Espacios',
        default=True,
        help='Eliminar espacios al inicio y final'
    )
    
    remove_line_breaks = fields.Boolean(
        string='Eliminar Saltos de Línea',
        default=True,
        help='Reemplazar saltos de línea por espacios'
    )
    
    uppercase = fields.Boolean(
        string='Mayúsculas',
        default=False,
        help='Convertir a mayúsculas'
    )
    
    notes = fields.Text(
        string='Notas/Documentación',
        help='Descripción del campo según documentación Nextbyn'
    )
    
    def _get_value_from_record(self, record):
        """
        Obtiene el valor del registro según la configuración del campo.
        """
        self.ensure_one()
        value = None
        
        try:
            if self.source_type == 'field' and self.field_id:
                value = record[self.field_id.name]
                
            elif self.source_type == 'related' and self.related_field_path:
                # Navegar por la ruta: partner_id.state_id.name
                obj = record
                for part in self.related_field_path.split('.'):
                    if obj:
                        obj = getattr(obj, part, None)
                value = obj
                
            elif self.source_type == 'expression' and self.python_expression:
                # Evaluar expresión Python
                from datetime import datetime, date
                local_vars = {
                    'record': record,
                    'env': self.env,
                    'datetime': datetime,
                    'date': date,
                }
                value = eval(self.python_expression, {"__builtins__": {}}, local_vars)
                
            elif self.source_type == 'fixed':
                value = self.fixed_value
                
            elif self.source_type == 'sequence':
                # Este se maneja en el generador principal
                value = 0
                
        except Exception as e:
            _logger.warning(f'Error obteniendo valor para {self.nextbyn_name}: {str(e)}')
            value = None
        
        # Aplicar valor por defecto si está vacío
        if value is None or value == '' or value is False:
            if self.default_value:
                value = self.default_value
        
        return value
    
    def _format_value(self, value):
        """
        Formatea el valor según el tipo de dato y configuración.
        """
        self.ensure_one()
        
        if value is None:
            return self.default_value or ''
        
        try:
            # Booleano
            if self.data_type == 'boolean':
                return self._format_boolean(value)
            
            # Fecha
            elif self.data_type == 'date':
                return self._format_date(value)
            
            # Fecha y hora
            elif self.data_type == 'datetime':
                return self._format_datetime(value)
            
            # Hora
            elif self.data_type == 'time':
                return self._format_time(value)
            
            # Entero
            elif self.data_type == 'integer':
                return str(int(value)) if value else '0'
            
            # Decimal
            elif self.data_type == 'float':
                return self._format_float(value)
            
            # Texto (default)
            else:
                return self._format_string(value)
                
        except Exception as e:
            _logger.warning(f'Error formateando {self.nextbyn_name}: {str(e)}')
            return self.default_value or ''
    
    def _format_boolean(self, value):
        """Formatea valor booleano"""
        is_true = bool(value)
        
        formats = {
            '01': ('0', '1'),
            'SINO_upper': ('NO', 'SI'),
            'YESNO_upper': ('NO', 'YES'),
            'sino_lower': ('no', 'si'),
            'yesno_lower': ('no', 'yes'),
            'truefalse': ('False', 'True'),
        }
        
        false_val, true_val = formats.get(self.bool_format, ('0', '1'))
        return true_val if is_true else false_val
    
    def _format_date(self, value):
        """Formatea valor de fecha"""
        if not value:
            return ''
        
        from datetime import date, datetime
        
        if isinstance(value, str):
            return value
        
        if isinstance(value, datetime):
            value = value.date()
        
        format_map = {
            'yyyy/MM/dd': '%Y/%m/%d',
            'dd/MM/yyyy': '%d/%m/%Y',
            'yyyy-MM-dd': '%Y-%m-%d',
            'dd-MM-yyyy': '%d-%m-%Y',
            'yyyyMMdd': '%Y%m%d',
        }
        
        fmt = format_map.get(self.date_format, '%Y/%m/%d')
        return value.strftime(fmt)
    
    def _format_datetime(self, value):
        """Formatea fecha y hora"""
        if not value:
            return ''
        
        from datetime import datetime
        
        if isinstance(value, str):
            return value
        
        date_part = self._format_date(value)
        time_part = value.strftime('%H:%M:%S') if hasattr(value, 'strftime') else ''
        
        return f'{date_part} {time_part}'.strip()
    
    def _format_time(self, value):
        """Formatea hora"""
        if not value:
            return ''
        
        from datetime import datetime, time
        
        if isinstance(value, str):
            return value
        
        format_map = {
            'HH:MM:SS': '%H:%M:%S',
            'HH:MM': '%H:%M',
            'HHMMSS': '%H%M%S',
        }
        
        fmt = format_map.get(self.time_format, '%H:%M:%S')
        
        if hasattr(value, 'strftime'):
            return value.strftime(fmt)
        
        return str(value)
    
    def _format_float(self, value):
        """Formatea número decimal"""
        if value is None:
            value = 0.0
        
        formatted = f'{float(value):.{self.decimal_places}f}'
        
        if self.decimal_separator == ',':
            formatted = formatted.replace('.', ',')
        
        return formatted
    
    def _format_string(self, value):
        """Formatea texto"""
        result = str(value) if value else ''
        
        if self.trim_spaces:
            result = result.strip()
        
        if self.remove_line_breaks:
            result = result.replace('\n', ' ').replace('\r', '')
        
        if self.uppercase:
            result = result.upper()
        
        if self.max_length and len(result) > self.max_length:
            result = result[:self.max_length]
        
        # Escapar separadores
        entity_sep = self.entity_id.separator
        if entity_sep in result:
            result = result.replace(entity_sep, ' ')
        
        return result
