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


class HrEmployeePublic(models.Model):
    """
    Espejo de los campos Nextbyn en el perfil público del empleado.

    hr.employee._check_private_fields() rechaza con AccessError cualquier campo
    que exista en hr.employee pero no acá. El POS lee pos.config -> hr.employee
    sin permisos de RRHH, cae en este modelo público y rompía la carga de datos
    (KeyError: 'pos.config'). Declarándolos como related el POS puede leerlos.
    """
    _inherit = 'hr.employee.public'

    x_softys_codigo = fields.Char(
        string='Código Personal Nextbyn',
        related='employee_id.x_softys_codigo',
        compute_sudo=True,
        readonly=True,
    )

    x_softys_cargo = fields.Selection(
        related='employee_id.x_softys_cargo',
        string='Cargo Nextbyn',
        compute_sudo=True,
        readonly=True,
    )

    x_softys_codigo_fuerza = fields.Integer(
        string='Código Fuerza',
        related='employee_id.x_softys_codigo_fuerza',
        compute_sudo=True,
        readonly=True,
    )

    x_softys_exportar = fields.Boolean(
        string='Exportar a Nextbyn',
        related='employee_id.x_softys_exportar',
        compute_sudo=True,
        readonly=True,
    )
