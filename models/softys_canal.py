# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SoftysCanal(models.Model):
    """
    Catálogo de Canales Softys.
    
    Del análisis del .ktr, los canales son:
    01, 02, 03, 04, 05, 06, 07, 08, 09
    """
    _name = 'softys.canal'
    _description = 'Canal Softys'
    _order = 'codigo'
    _rec_name = 'display_name'
    
    codigo = fields.Char(
        string='Código',
        required=True,
        size=2,
        help='Código de canal (2 dígitos, ej: 01, 02, ...)'
    )
    
    nombre = fields.Char(
        string='Nombre',
        required=True,
        help='Nombre descriptivo del canal'
    )
    
    descripcion = fields.Text(
        string='Descripción',
        help='Descripción detallada del canal'
    )
    
    active = fields.Boolean(
        string='Activo',
        default=True
    )
    
    display_name = fields.Char(
        string='Nombre Completo',
        compute='_compute_display_name',
        store=True
    )
    
    subcanal_ids = fields.One2many(
        'softys.subcanal',
        'canal_id',
        string='Subcanales'
    )
    
    subcanal_count = fields.Integer(
        string='Total Subcanales',
        compute='_compute_subcanal_count'
    )
    
    @api.depends('codigo', 'nombre')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f'[{record.codigo}] {record.nombre}'
    
    @api.depends('subcanal_ids')
    def _compute_subcanal_count(self):
        for record in self:
            record.subcanal_count = len(record.subcanal_ids)
    
    @api.constrains('codigo')
    def _check_codigo_format(self):
        for record in self:
            if not record.codigo or len(record.codigo) != 2:
                raise ValidationError(
                    _('El código del canal debe tener exactamente 2 dígitos.')
                )
            if not record.codigo.isdigit():
                raise ValidationError(
                    _('El código del canal debe ser numérico.')
                )
    
    _sql_constraints = [
        ('unique_codigo',
         'UNIQUE(codigo)',
         'El código de canal debe ser único.')
    ]


class SoftysSubcanal(models.Model):
    """
    Catálogo de Subcanales Softys.
    
    Del análisis del .ktr, hay más de 100 subcanales diferentes
    distribuidos entre los 9 canales.
    """
    _name = 'softys.subcanal'
    _description = 'Subcanal Softys'
    _order = 'canal_id, codigo'
    _rec_name = 'display_name'
    
    canal_id = fields.Many2one(
        'softys.canal',
        string='Canal',
        required=True,
        ondelete='cascade',
        help='Canal al que pertenece este subcanal'
    )
    
    codigo = fields.Char(
        string='Código',
        required=True,
        size=2,
        help='Código de subcanal (2 dígitos, ej: 01, 07, 09, ...)'
    )
    
    nombre = fields.Char(
        string='Nombre',
        required=True,
        help='Nombre descriptivo del subcanal'
    )
    
    descripcion = fields.Text(
        string='Descripción',
        help='Descripción detallada del subcanal'
    )
    
    active = fields.Boolean(
        string='Activo',
        default=True
    )
    
    display_name = fields.Char(
        string='Nombre Completo',
        compute='_compute_display_name',
        store=True
    )
    
    # Ejemplos de actividades que mapean a este subcanal
    ejemplo_actividades = fields.Text(
        string='Ejemplos Actividades',
        help='Ejemplos de actividades que mapean a este subcanal (referencia)'
    )
    
    @api.depends('canal_id.codigo', 'codigo', 'nombre')
    def _compute_display_name(self):
        for record in self:
            if record.canal_id:
                record.display_name = f'[{record.canal_id.codigo}-{record.codigo}] {record.nombre}'
            else:
                record.display_name = f'[{record.codigo}] {record.nombre}'
    
    @api.constrains('codigo')
    def _check_codigo_format(self):
        for record in self:
            if not record.codigo or len(record.codigo) != 2:
                raise ValidationError(
                    _('El código del subcanal debe tener exactamente 2 dígitos.')
                )
            if not record.codigo.isdigit():
                raise ValidationError(
                    _('El código del subcanal debe ser numérico.')
                )
    
    _sql_constraints = [
        ('unique_codigo_per_canal',
         'UNIQUE(canal_id, codigo)',
         'El código de subcanal debe ser único dentro del mismo canal.')
    ]
