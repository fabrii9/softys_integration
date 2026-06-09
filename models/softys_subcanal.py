# -*- coding: utf-8 -*-

from odoo import models, fields, api


class SoftysSubcanal(models.Model):
    """
    Subcanal comercial para categorización de clientes según Nextbyn.
    """
    _name = 'softys.subcanal'
    _description = 'Subcanal Nextbyn'
    _order = 'canal_id, codigo'
    
    canal_id = fields.Many2one(
        'softys.canal',
        string='Canal',
        required=True,
        ondelete='cascade'
    )
    
    codigo = fields.Char(
        string='Código',
        required=True,
        size=10
    )
    
    nombre = fields.Char(
        string='Nombre',
        required=True,
        size=100
    )
    
    active = fields.Boolean(
        string='Activo',
        default=True
    )
    
    _sql_constraints = [
        ('canal_codigo_unique', 'unique(canal_id, codigo)', 
         'El código de subcanal debe ser único dentro del canal.')
    ]
