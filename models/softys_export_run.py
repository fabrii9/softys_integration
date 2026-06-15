# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import csv
import io
import os
from datetime import datetime, timedelta
import base64

_logger = logging.getLogger(__name__)


class SoftysExportRun(models.Model):
    """
    Representa una ejecución de exportación Softys.
    Orquesta la generación de los 7 archivos CSV.
    """
    _name = 'softys.export.run'
    _description = 'Ejecución Exportación Softys'
    _order = 'create_date desc'
    _rec_name = 'display_name'
    
    connector_id = fields.Many2one(
        'softys.connector',
        string='Conector',
        required=True,
        ondelete='cascade'
    )
    
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('running', 'En Ejecución'),
        ('done', 'Completado'),
        ('failed', 'Fallido'),
    ], string='Estado', default='draft', required=True)
    
    start_date = fields.Datetime(
        string='Fecha Inicio',
        readonly=True
    )
    
    end_date = fields.Datetime(
        string='Fecha Fin',
        readonly=True
    )
    
    duration = fields.Float(
        string='Duración (seg)',
        compute='_compute_duration',
        store=True
    )
    
    # Archivos generados
    file_ids = fields.One2many(
        'softys.export.file',
        'run_id',
        string='Archivos Generados'
    )
    
    file_count = fields.Integer(
        string='Total Archivos',
        compute='_compute_file_count'
    )
    
    # Estadísticas
    total_clientes = fields.Integer(
        string='Total Clientes',
        readonly=True
    )
    
    total_articulos = fields.Integer(
        string='Total Artículos',
        readonly=True
    )
    
    total_comprobantes = fields.Integer(
        string='Total Comprobantes',
        readonly=True
    )
    
    total_lineas = fields.Integer(
        string='Total Líneas Comprobantes',
        readonly=True
    )
    
    total_personal = fields.Integer(
        string='Total Personal Comercial',
        readonly=True
    )
    
    total_clientes_ruta = fields.Integer(
        string='Total Clientes Ruta',
        readonly=True
    )
    
    total_rutas = fields.Integer(
        string='Total Rutas',
        readonly=True
    )
    
    total_stock = fields.Integer(
        string='Total Stock Físico',
        readonly=True
    )
    
    # Logs
    log_ids = fields.One2many(
        'softys.export.log',
        'run_id',
        string='Logs'
    )
    
    error_count = fields.Integer(
        string='Total Errores',
        compute='_compute_error_count'
    )
    
    warning_count = fields.Integer(
        string='Total Advertencias',
        compute='_compute_error_count'
    )
    
    notes = fields.Text(
        string='Notas'
    )
    
    display_name = fields.Char(
        string='Nombre',
        compute='_compute_display_name'
    )
    
    @api.depends('connector_id', 'create_date')
    def _compute_display_name(self):
        for record in self:
            if record.connector_id and record.create_date:
                date_str = fields.Datetime.to_string(record.create_date)
                record.display_name = f'{record.connector_id.company_code} - {date_str}'
            else:
                record.display_name = f'Export #{record.id}'
    
    @api.depends('start_date', 'end_date')
    def _compute_duration(self):
        for record in self:
            if record.start_date and record.end_date:
                delta = record.end_date - record.start_date
                record.duration = delta.total_seconds()
            else:
                record.duration = 0.0
    
    @api.depends('file_ids')
    def _compute_file_count(self):
        for record in self:
            record.file_count = len(record.file_ids)
    
    @api.depends('log_ids', 'log_ids.level')
    def _compute_error_count(self):
        for record in self:
            record.error_count = len(record.log_ids.filtered(
                lambda l: l.level == 'error'
            ))
            record.warning_count = len(record.log_ids.filtered(
                lambda l: l.level == 'warning'
            ))
    
    def action_run_export(self):
        """Ejecutar la exportación usando el motor Nextbyn"""
        self.ensure_one()
        
        if self.state != 'draft':
            raise UserError(_('Solo se pueden ejecutar exportaciones en estado Borrador'))
        
        try:
            self.write({
                'state': 'running',
                'start_date': fields.Datetime.now(),
            })
            self._log('info', 'Iniciando exportación Nextbyn (documentación oficial)')
            
            # Crear directorio de salida
            self.connector_id._create_output_directory()
            
            # Obtener el motor de exportación Nextbyn
            engine = self.env['nextbyn.export.engine']
            
            # Rango de fechas para comprobantes según configuración del conector
            days_back = self.connector_id.days_back or 30
            date_from = fields.Date.today() - timedelta(days=days_back)
            date_to = fields.Date.today()
            
            # Ejecutar exportación completa
            results = engine.export_all(self.connector_id, date_from, date_to)
            
            # Guardar cada archivo generado
            for filename, content, row_count in results:
                if content:
                    file_type = self._get_file_type_from_filename(filename)
                    self._save_csv_content(filename, content, file_type)
                    self._log('info', f'{filename}: {row_count} registros exportados')
            
            # Finalizar
            self.write({
                'state': 'done',
                'end_date': fields.Datetime.now(),
            })
            
            # Actualizar conector
            self.connector_id.write({
                'last_export_date': fields.Datetime.now(),
                'last_export_status': 'success' if self.error_count == 0 else 'partial',
            })
            
            self._log('info', f'Exportación completada. {self.file_count} archivos generados.')
            
        except Exception as e:
            self.write({
                'state': 'failed',
                'end_date': fields.Datetime.now(),
            })
            self.connector_id.write({
                'last_export_date': fields.Datetime.now(),
                'last_export_status': 'failed',
            })
            self._log('error', f'Error en exportación: {str(e)}')
            raise
    
    def _get_file_type_from_filename(self, filename):
        """Determina el tipo de archivo desde el nombre."""
        filename_lower = filename.lower()
        if 'articulos' in filename_lower:
            return 'articulos'
        elif 'clientes' in filename_lower and 'ruta' not in filename_lower:
            return 'clientes'
        elif 'comprobantes' in filename_lower:
            return 'comprobantes'
        elif 'personal' in filename_lower:
            return 'personal_comercial'
        elif 'clientesruta' in filename_lower:
            return 'clientes_ruta'
        elif 'rutas' in filename_lower:
            return 'rutas_venta'
        elif 'stock' in filename_lower:
            return 'stock_fisico'
        return 'custom'
    
    def _save_csv_content(self, filename, content, file_type):
        """Guardar contenido CSV en filesystem y/o attachment"""
        connector = self.connector_id
        
        # Contar filas (excluir header)
        lines = content.strip().split('\n')
        row_count = len(lines) - 1 if len(lines) > 1 else 0
        
        # Codificar
        encoding = connector.csv_encoding or 'utf-8'
        try:
            csv_bytes = content.encode(encoding)
        except Exception as e:
            self._log('warning', f'Error codificando con {encoding}, usando UTF-8: {str(e)}')
            csv_bytes = content.encode('utf-8')
        
        # Guardar en filesystem
        if connector.output_storage_type in ('filesystem', 'both'):
            filepath = os.path.join(connector.output_path, filename)
            try:
                with open(filepath, 'wb') as f:
                    f.write(csv_bytes)
                self._log('info', f'Archivo guardado: {filepath}')
            except Exception as e:
                self._log('error', f'Error guardando {filepath}: {str(e)}')
        
        # Guardar como attachment
        if connector.output_storage_type in ('attachment', 'both'):
            self.env['softys.export.file'].create({
                'run_id': self.id,
                'name': filename,
                'file_type': file_type,
                'datas': base64.b64encode(csv_bytes),
                'row_count': row_count,
            })
        
        return row_count
    
    def _log(self, level, message):
        """Agregar log a la ejecución"""
        self.env['softys.export.log'].create({
            'run_id': self.id,
            'level': level,
            'message': message,
        })
        
        if level == 'error':
            _logger.error(f'Softys Export [{self.id}]: {message}')
        elif level == 'warning':
            _logger.warning(f'Softys Export [{self.id}]: {message}')
        else:
            _logger.info(f'Softys Export [{self.id}]: {message}')
    
    def _create_csv_file(self, filename, headers, rows, template=None):
        """
        Crear archivo CSV y guardarlo como adjunto.
        
        Args:
            filename: Nombre del archivo (sin extensión)
            headers: Lista de nombres de columnas
            rows: Lista de listas con los datos
            template: softys.export.template opcional para configuración
        """
        connector = self.connector_id
        
        # Determinar encoding y separador
        if template:
            encoding = template.encoding or connector.csv_encoding
            separator = template.separator or connector.csv_separator
            enclosure = template.enclosure or connector.csv_enclosure
        else:
            encoding = connector.csv_encoding
            separator = connector.csv_separator
            enclosure = connector.csv_enclosure
        
        # Crear contenido CSV
        output = io.StringIO()
        writer = csv.writer(
            output,
            delimiter=separator,
            quotechar=enclosure if enclosure else '"',
            quoting=csv.QUOTE_MINIMAL if enclosure else csv.QUOTE_NONE,
            escapechar='\\' if not enclosure else None
        )
        
        # Escribir header si está configurado
        if template and template.header:
            writer.writerow(headers)
        
        # Escribir datos
        for row in rows:
            writer.writerow(row)
        
        csv_content = output.getvalue()
        output.close()
        
        # Codificar según encoding
        try:
            csv_bytes = csv_content.encode(encoding)
        except Exception as e:
            self._log('warning', f'Error codificando {filename} con {encoding}, usando UTF-8: {str(e)}')
            csv_bytes = csv_content.encode('utf-8')
        
        # Guardar en filesystem si está configurado
        full_filename = f'{filename}.csv'
        if connector.output_storage_type in ('filesystem', 'both'):
            filepath = os.path.join(connector.output_path, full_filename)
            try:
                with open(filepath, 'wb') as f:
                    f.write(csv_bytes)
                self._log('info', f'Archivo guardado: {filepath}')
            except Exception as e:
                self._log('error', f'Error guardando archivo {filepath}: {str(e)}')
        
        # Guardar como adjunto si está configurado
        if connector.output_storage_type in ('attachment', 'both'):
            self.env['softys.export.file'].create({
                'run_id': self.id,
                'name': full_filename,
                'file_type': template.file_type if template else 'custom',
                'datas': base64.b64encode(csv_bytes),
                'row_count': len(rows),
            })
        
        return len(rows)


class SoftysExportFile(models.Model):
    """Archivo generado en una exportación"""
    _name = 'softys.export.file'
    _description = 'Archivo Exportación Softys'
    _order = 'create_date desc'
    
    run_id = fields.Many2one(
        'softys.export.run',
        string='Ejecución',
        required=True,
        ondelete='cascade'
    )
    
    name = fields.Char(
        string='Nombre Archivo',
        required=True
    )
    
    file_type = fields.Selection([
        ('clientes', 'Clientes'),
        ('articulos', 'Artículos'),
        ('comprobantes', 'Comprobantes'),
        ('personal_comercial', 'Personal Comercial'),
        ('clientes_ruta', 'Clientes Ruta'),
        ('rutas_venta', 'Rutas de Venta'),
        ('stock_fisico', 'Stock Físico'),
        ('custom', 'Personalizado'),
    ], string='Tipo', required=True)
    
    datas = fields.Binary(
        string='Archivo'
    )
    
    row_count = fields.Integer(
        string='Total Filas',
        readonly=True
    )
    
    file_size = fields.Integer(
        string='Tamaño (bytes)',
        compute='_compute_file_size'
    )
    
    @api.depends('datas')
    def _compute_file_size(self):
        for record in self:
            if not record.datas:
                record.file_size = 0
                continue
            try:
                record.file_size = len(base64.b64decode(record.datas))
            except Exception:
                # Si no es base64 válido (p. ej. referencia de attachment),
                # usamos el tamaño del valor crudo como aproximación.
                record.file_size = len(record.datas) if isinstance(record.datas, (str, bytes)) else 0


class SoftysExportLog(models.Model):
    """Log de una ejecución de exportación"""
    _name = 'softys.export.log'
    _description = 'Log Exportación Softys'
    _order = 'create_date desc'
    
    run_id = fields.Many2one(
        'softys.export.run',
        string='Ejecución',
        required=True,
        ondelete='cascade',
        index=True
    )
    
    level = fields.Selection([
        ('info', 'Info'),
        ('warning', 'Advertencia'),
        ('error', 'Error'),
    ], string='Nivel', required=True, default='info', index=True)
    
    message = fields.Text(
        string='Mensaje',
        required=True
    )
    
    create_date = fields.Datetime(
        string='Fecha',
        readonly=True
    )
