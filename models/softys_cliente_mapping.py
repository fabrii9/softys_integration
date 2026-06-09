# -*- coding: utf-8 -*-

from odoo import models, fields, api


class SoftysClienteMapping(models.Model):
    """
    Mapeo de clientes Odoo a códigos Nextbyn.
    Permite mantener códigos originales de sistemas legacy.
    """
    _name = 'softys.cliente.mapping'
    _description = 'Mapeo Cliente Nextbyn'
    _order = 'partner_id'
    
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente Odoo',
        required=True,
        ondelete='cascade'
    )
    
    softys_codigo = fields.Char(
        string='Código Nextbyn',
        required=True,
        size=50,
        help='Código del cliente en sistema Nextbyn/YAS'
    )
    
    yas_idcliente = fields.Integer(
        string='ID Cliente YAS',
        help='ID original del cliente en sistema YAS (migración)'
    )
    
    notes = fields.Text(
        string='Notas'
    )
    
    _sql_constraints = [
        ('partner_unique', 'unique(partner_id)', 
         'Ya existe un mapeo para este cliente.'),
        ('codigo_unique', 'unique(softys_codigo)', 
         'El código Nextbyn ya está asignado a otro cliente.'),
    ]
