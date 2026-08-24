# -*- coding: utf-8 -*-

from odoo import models, fields, api


class SoftysLocalidad(models.Model):
    """
    Catálogo de localidades del Anexo "Ciudades argentinas v2" de Nextbyn.
    Se usa para CodigoLocalidad/DescripcionLocalidad/CodigoProvincia/
    DescProvincia del archivo Clientes (instructivo V2.4.2).
    """
    _name = 'softys.localidad'
    _description = 'Localidad Nextbyn (Anexo Ciudades Argentinas)'
    _order = 'provincia_nombre, nombre'
    _rec_name = 'display_name'

    id_localidad = fields.Integer(
        string='ID Localidad',
        required=True,
        index=True,
        help='IdLocalidad según Anexo Nextbyn (CodigoLocalidad en CSV)'
    )

    nombre = fields.Char(
        string='Localidad',
        required=True,
        index=True,
        help='DescripcionLocalidad'
    )

    id_provincia = fields.Integer(
        string='ID Provincia',
        required=True,
        index=True,
        help='idprovincia según Anexo Nextbyn (CodigoProvincia en CSV)'
    )

    provincia_nombre = fields.Char(
        string='Provincia',
        required=True,
        index=True,
        help='DescProvincia'
    )

    display_name = fields.Char(
        string='Nombre Completo',
        compute='_compute_display_name',
        store=True
    )

    _sql_constraints = [
        ('id_localidad_unique', 'unique(id_localidad)',
         'El ID de localidad debe ser único.')
    ]

    @api.depends('nombre', 'provincia_nombre')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f'{record.nombre} ({record.provincia_nombre})'
