# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SoftysExportWizard(models.TransientModel):
    """
    Wizard para ejecutar exportación manual a Softys.
    Solo pregunta por el conector; exporta siempre los 7 archivos obligatorios.
    """
    _name = 'softys.export.wizard'
    _description = 'Asistente Exportación Softys'
    
    connector_id = fields.Many2one(
        'softys.connector',
        string='Conector',
        required=True,
        default=lambda self: self._default_connector()
    )
    
    @api.model
    def _default_connector(self):
        """Obtener conector por defecto"""
        connector_id = self.env.context.get('default_connector_id')
        if connector_id:
            return connector_id
        
        # Buscar primer conector activo
        connector = self.env['softys.connector'].search([
            ('active', '=', True)
        ], limit=1)
        
        return connector.id if connector else False
    
    def action_export(self):
        """Ejecutar la exportación completa"""
        self.ensure_one()
        
        if not self.connector_id:
            raise UserError(_('Debe seleccionar un conector.'))
        
        # Crear registro de ejecución
        run = self.env['softys.export.run'].create({
            'connector_id': self.connector_id.id,
            'state': 'draft',
        })
        
        # Ejecutar exportación completa
        run.action_run_export()
        
        # Retornar acción para ver el resultado
        return {
            'name': _('Resultado Exportación'),
            'type': 'ir.actions.act_window',
            'res_model': 'softys.export.run',
            'res_id': run.id,
            'view_mode': 'form',
            'target': 'current',
        }
