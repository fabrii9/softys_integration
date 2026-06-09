# -*- coding: utf-8 -*-
"""
Extensiones a modelos Odoo para integración Nextbyn.
account.move se define aquí para campos de facturación.
stock.warehouse y hr.employee se definen en sus respectivos archivos.
"""

from odoo import models, fields, api


class AccountMove(models.Model):
    """
    Extensión de account.move para campos específicos de integración Nextbyn.
    """
    _inherit = 'account.move'
    
    x_softys_idfactura = fields.Integer(
        string='ID Factura YAS',
        help='ID original de la factura en sistema YAS (migración)',
        copy=False
    )
    
    x_softys_vendedor_id = fields.Many2one(
        'hr.employee',
        string='Vendedor',
        help='Vendedor asignado a esta factura (CodigoPersonal en Nextbyn)'
    )
    
    x_softys_exported = fields.Boolean(
        string='Exportado a Nextbyn',
        default=False,
        help='Indica si esta factura ya fue exportada a Nextbyn',
        copy=False
    )
    
    x_softys_export_date = fields.Datetime(
        string='Fecha Exportación',
        readonly=True,
        copy=False,
        help='Fecha y hora de la última exportación a Nextbyn'
    )


class AccountMoveLine(models.Model):
    """
    Extensión de account.move.line para campos Nextbyn.
    """
    _inherit = 'account.move.line'
    
    x_softys_exported = fields.Boolean(
        string='Exportado a Nextbyn',
        related='move_id.x_softys_exported',
        store=True,
        help='Indica si esta línea fue exportada a Nextbyn'
    )
