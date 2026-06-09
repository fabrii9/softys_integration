# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SoftysExportRule(models.Model):
    """
    Reglas de exportación para filtrar datos.
    Permite definir qué registros se exportan.
    """
    _name = 'softys.export.rule'
    _description = 'Regla Exportación Nextbyn'
    _order = 'sequence, name'
    
    name = fields.Char(
        string='Nombre',
        required=True
    )
    
    sequence = fields.Integer(
        string='Secuencia',
        default=10
    )
    
    active = fields.Boolean(
        string='Activo',
        default=True
    )
    
    connector_id = fields.Many2one(
        'softys.connector',
        string='Conector',
        ondelete='cascade'
    )
    
    model_id = fields.Many2one(
        'ir.model',
        string='Modelo',
        required=True,
        ondelete='cascade',
        domain=[('model', 'in', [
            'res.partner',
            'product.product',
            'account.move',
            'stock.quant',
        ])]
    )
    
    domain = fields.Text(
        string='Dominio',
        default='[]',
        help='Dominio en formato Python para filtrar registros'
    )
    
    notes = fields.Text(
        string='Notas'
    )
    
    @api.constrains('domain')
    def _check_domain(self):
        for rule in self:
            try:
                domain = eval(rule.domain or '[]')
                if not isinstance(domain, list):
                    raise ValidationError(_('El dominio debe ser una lista.'))
            except Exception as e:
                raise ValidationError(_(f'Dominio inválido: {str(e)}'))
    
    def get_records(self):
        """Retorna los registros que cumplen la regla."""
        self.ensure_one()
        domain = eval(self.domain or '[]')
        return self.env[self.model_id.model].search(domain)
