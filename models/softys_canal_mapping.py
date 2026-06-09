# -*- coding: utf-8 -*-

from odoo import models, fields, api


class SoftysCanalMapping(models.Model):
    """
    Mapeo de actividades a canales/subcanales.
    Según documentación: 88 actividades diferentes mapeadas.
    """
    _name = 'softys.canal.mapping'
    _description = 'Mapeo Actividad-Canal Nextbyn'
    _order = 'actividad'
    
    actividad = fields.Char(
        string='Actividad',
        required=True,
        size=100,
        help='Actividad comercial del cliente (de YAS)'
    )
    
    canal_id = fields.Many2one(
        'softys.canal',
        string='Canal',
        required=True,
        ondelete='restrict'
    )
    
    subcanal_id = fields.Many2one(
        'softys.subcanal',
        string='Subcanal',
        ondelete='restrict',
        domain="[('canal_id', '=', canal_id)]"
    )
    
    active = fields.Boolean(
        string='Activo',
        default=True
    )
    
    _sql_constraints = [
        ('actividad_unique', 'unique(actividad)', 
         'Ya existe un mapeo para esta actividad.'),
    ]
    
    @api.model
    def get_canal_subcanal(self, actividad):
        """
        Obtiene canal y subcanal para una actividad.
        Retorna (codigo_canal, codigo_subcanal) o (None, None).
        """
        if not actividad:
            return None, None
        
        mapping = self.search([
            ('actividad', '=ilike', actividad)
        ], limit=1)
        
        if mapping:
            canal_code = mapping.canal_id.codigo if mapping.canal_id else None
            subcanal_code = mapping.subcanal_id.codigo if mapping.subcanal_id else None
            return canal_code, subcanal_code
        
        return None, None
