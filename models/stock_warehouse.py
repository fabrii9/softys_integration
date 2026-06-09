# -*- coding: utf-8 -*-

from odoo import models, fields, api


class StockWarehouse(models.Model):
    """
    Extensión de stock.warehouse para campos Nextbyn.
    """
    _inherit = 'stock.warehouse'
    
    x_softys_codigo_deposito = fields.Char(
        string='Código Depósito Nextbyn',
        size=10,
        help='Código del depósito para exportación Nextbyn (CodigoDeposito)'
    )
    
    x_softys_exportar = fields.Boolean(
        string='Exportar a Nextbyn',
        default=True,
        help='Indica si este depósito se exporta a Nextbyn'
    )


class StockLocation(models.Model):
    """
    Extensión de stock.location para código de depósito.
    """
    _inherit = 'stock.location'
    
    x_softys_codigo_deposito = fields.Char(
        string='Código Depósito Nextbyn',
        size=10,
        help='Código del depósito para exportación Nextbyn'
    )
