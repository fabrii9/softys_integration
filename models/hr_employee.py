# -*- coding: utf-8 -*-

from odoo import models, fields, api


class HrEmployee(models.Model):
    """
    Extensión de hr.employee para campos Nextbyn/Personal Comercial.
    """
    _inherit = 'hr.employee'
    
    x_softys_codigo = fields.Char(
        string='Código Personal Nextbyn',
        size=20,
        help='Código del empleado para exportación Nextbyn (CodigoPersonal)'
    )
    
    x_softys_cargo = fields.Selection([
        ('V', 'Vendedor'),
        ('S', 'Supervisor'),
        ('G', 'Gerente'),
        ('F', 'Fletero/Repartidor'),
    ], string='Cargo Nextbyn',
       help='Cargo del empleado para Nextbyn')
    
    x_softys_codigo_fuerza = fields.Integer(
        string='Código Fuerza',
        help='Código de fuerza de venta'
    )
    
    x_softys_exportar = fields.Boolean(
        string='Exportar a Nextbyn',
        default=False,
        help='Indica si este empleado se exporta como Personal Comercial'
    )
