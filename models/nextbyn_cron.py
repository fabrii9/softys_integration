# -*- coding: utf-8 -*-
"""
Cron y ejecución programada de exportaciones Nextbyn.
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import os
import base64
from datetime import datetime

_logger = logging.getLogger(__name__)


class NextbynExportCron(models.Model):
    """
    Modelo para gestionar exportaciones programadas de Nextbyn.
    Permite configurar y ejecutar exportaciones por cron.
    """
    _name = 'nextbyn.export.cron'
    _description = 'Configuración Cron Nextbyn'
    _order = 'name'
    
    name = fields.Char(
        string='Nombre',
        required=True,
        default='Exportación Nextbyn'
    )
    
    active = fields.Boolean(
        string='Activo',
        default=True
    )
    
    connector_id = fields.Many2one(
        'softys.connector',
        string='Conector',
        required=True,
        help='Conector con la configuración de empresa y rutas'
    )
    
    # Entidades a exportar
    entity_ids = fields.Many2many(
        'nextbyn.export.entity',
        'nextbyn_cron_entity_rel',
        'cron_id',
        'entity_id',
        string='Entidades a Exportar',
        help='Entidades que se exportarán con este cron'
    )
    
    export_all_entities = fields.Boolean(
        string='Exportar Todas',
        default=True,
        help='Si está activo, exporta todas las entidades activas'
    )
    
    # Configuración de salida
    output_type = fields.Selection([
        ('filesystem', 'Sistema de Archivos'),
        ('attachment', 'Adjuntos en Odoo'),
        ('both', 'Ambos'),
    ], string='Destino',
       default='both',
       required=True)
    
    output_path = fields.Char(
        string='Ruta de Salida',
        help='Ruta donde se guardarán los archivos CSV'
    )
    
    # Historial
    last_run = fields.Datetime(
        string='Última Ejecución',
        readonly=True
    )
    
    last_run_status = fields.Selection([
        ('success', 'Exitoso'),
        ('partial', 'Parcial'),
        ('failed', 'Fallido'),
    ], string='Estado Última Ejecución',
       readonly=True)
    
    last_run_message = fields.Text(
        string='Mensaje',
        readonly=True
    )
    
    run_count = fields.Integer(
        string='Ejecuciones',
        default=0,
        readonly=True
    )
    
    # Relación con cron de Odoo
    ir_cron_id = fields.Many2one(
        'ir.cron',
        string='Tarea Programada',
        readonly=True,
        ondelete='set null'
    )
    
    cron_active = fields.Boolean(
        string='Cron Activo',
        compute='_compute_cron_active',
        inverse='_set_cron_active'
    )
    
    cron_interval = fields.Integer(
        string='Intervalo',
        default=1
    )
    
    cron_interval_type = fields.Selection([
        ('minutes', 'Minutos'),
        ('hours', 'Horas'),
        ('days', 'Días'),
        ('weeks', 'Semanas'),
        ('months', 'Meses'),
    ], string='Tipo Intervalo',
       default='days')
    
    cron_nextcall = fields.Datetime(
        string='Próxima Ejecución',
        related='ir_cron_id.nextcall',
        readonly=True
    )
    
    @api.depends('ir_cron_id', 'ir_cron_id.active')
    def _compute_cron_active(self):
        for rec in self:
            rec.cron_active = rec.ir_cron_id.active if rec.ir_cron_id else False
    
    def _set_cron_active(self):
        for rec in self:
            if rec.ir_cron_id:
                rec.ir_cron_id.active = rec.cron_active
    
    def action_create_cron(self):
        """Crear tarea programada de Odoo"""
        self.ensure_one()
        
        if self.ir_cron_id:
            raise UserError(_('Ya existe una tarea programada para esta configuración.'))
        
        cron = self.env['ir.cron'].create({
            'name': f'Nextbyn: {self.name}',
            'model_id': self.env.ref('softys_integration.model_nextbyn_export_cron').id,
            'state': 'code',
            'code': f'model.browse({self.id}).execute_export()',
            'interval_number': self.cron_interval,
            'interval_type': self.cron_interval_type,
            'numbercall': -1,
            'active': False,
            'doall': False,
        })
        
        self.ir_cron_id = cron.id
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('Tarea programada creada. Actívela cuando esté listo.'),
                'type': 'success',
            }
        }
    
    def action_run_now(self):
        """Ejecutar exportación manualmente"""
        self.ensure_one()
        return self.execute_export()
    
    def execute_export(self):
        """
        Ejecuta la exportación de las entidades configuradas.
        Llamado por el cron o manualmente.
        """
        self.ensure_one()
        
        _logger.info(f'Iniciando exportación Nextbyn: {self.name}')
        
        results = []
        errors = []
        
        try:
            # Obtener entidades a exportar
            if self.export_all_entities:
                entities = self.env['nextbyn.export.entity'].search([
                    ('active', '=', True)
                ])
            else:
                entities = self.entity_ids.filtered('active')
            
            if not entities:
                raise UserError(_('No hay entidades configuradas para exportar.'))
            
            # Obtener configuración
            company_code = self.connector_id.company_code or '000001'
            output_path = self.output_path or self.connector_id.output_path or '/tmp'
            
            # Crear directorio si no existe
            if self.output_type in ('filesystem', 'both'):
                os.makedirs(output_path, exist_ok=True)
            
            # Exportar cada entidad
            for entity in entities:
                try:
                    content, count = entity._generate_csv_content()
                    filename = entity._get_filename(company_code)
                    
                    # Guardar archivo
                    if self.output_type in ('filesystem', 'both'):
                        filepath = os.path.join(output_path, filename)
                        with open(filepath, 'w', encoding=entity.encoding) as f:
                            f.write(content)
                        _logger.info(f'Archivo guardado: {filepath}')
                    
                    # Crear adjunto
                    if self.output_type in ('attachment', 'both'):
                        self.env['ir.attachment'].create({
                            'name': filename,
                            'type': 'binary',
                            'datas': base64.b64encode(content.encode(entity.encoding)),
                            'res_model': 'nextbyn.export.cron',
                            'res_id': self.id,
                            'mimetype': 'text/csv',
                        })
                    
                    results.append(f'{entity.name}: {count} registros')
                    
                except Exception as e:
                    error_msg = f'{entity.name}: {str(e)}'
                    errors.append(error_msg)
                    _logger.error(f'Error exportando {entity.name}: {str(e)}')
            
            # Actualizar estado
            status = 'failed' if not results else ('partial' if errors else 'success')
            message = '\n'.join(results + errors) if results or errors else 'Sin resultados'
            
            self.write({
                'last_run': fields.Datetime.now(),
                'last_run_status': status,
                'last_run_message': message,
                'run_count': self.run_count + 1,
            })
            
            _logger.info(f'Exportación completada: {status}')
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Exportación Completada'),
                    'message': message,
                    'type': 'success' if status == 'success' else 'warning',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            self.write({
                'last_run': fields.Datetime.now(),
                'last_run_status': 'failed',
                'last_run_message': str(e),
            })
            _logger.error(f'Error en exportación: {str(e)}')
            raise
    
    @api.model
    def run_scheduled_export(self):
        """
        Método llamado por el cron principal.
        Ejecuta todas las configuraciones activas.
        """
        configs = self.search([('active', '=', True)])
        for config in configs:
            try:
                config.execute_export()
            except Exception as e:
                _logger.error(f'Error en cron {config.name}: {str(e)}')
    
    @api.model
    def run_entity_export(self, entity_name):
        """
        Exportar una entidad específica desde cron.
        """
        entity = self.env['nextbyn.export.entity'].search([
            ('name', '=', entity_name),
            ('active', '=', True)
        ], limit=1)
        
        if not entity:
            _logger.warning(f'Entidad {entity_name} no encontrada o inactiva')
            return
        
        # Buscar configuración activa
        config = self.search([('active', '=', True)], limit=1)
        if not config:
            _logger.warning('No hay configuración de cron activa')
            return
        
        # Ejecutar solo esta entidad
        try:
            content, count = entity._generate_csv_content()
            filename = entity._get_filename(config.connector_id.company_code or '000001')
            output_path = config.output_path or config.connector_id.output_path or '/tmp'
            
            # Guardar
            os.makedirs(output_path, exist_ok=True)
            filepath = os.path.join(output_path, filename)
            with open(filepath, 'w', encoding=entity.encoding) as f:
                f.write(content)
            
            _logger.info(f'Exportado {entity_name}: {count} registros -> {filepath}')
            
        except Exception as e:
            _logger.error(f'Error exportando {entity_name}: {str(e)}')
