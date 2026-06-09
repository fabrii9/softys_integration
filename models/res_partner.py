# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResPartner(models.Model):
    """
    Extensión de res.partner para campos específicos de integración Nextbyn.
    Según documentación oficial de Nextbyn - entidad Clientes.
    """
    _inherit = 'res.partner'
    
    # Campos de YAS (migración)
    x_softys_idcliente = fields.Integer(
        string='ID Cliente YAS',
        help='ID original del cliente en sistema YAS',
        copy=False
    )
    
    # === CAMPOS PARA CSV CLIENTES DE NEXTBYN ===
    
    x_softys_codigo = fields.Char(
        string='Código Cliente',
        compute='_compute_softys_codigo',
        store=True,
        help='CodigoCliente - Código único del cliente para Nextbyn'
    )
    
    x_softys_razon_social = fields.Char(
        string='Razón Social Nextbyn',
        compute='_compute_razon_social',
        store=True,
        help='RazonSocial - Se toma del name del partner'
    )
    
    x_softys_nombre_comercial = fields.Char(
        string='Nombre Comercial',
        help='NombreComercial - Nombre de fantasía del negocio'
    )
    
    x_softys_tipo_documento = fields.Selection([
        ('DNI', 'DNI'),
        ('CUIT', 'CUIT'),
        ('CUIL', 'CUIL'),
        ('CI', 'Cédula Identidad'),
        ('RUT', 'RUT'),
        ('RUC', 'RUC'),
        ('PAS', 'Pasaporte'),
    ], string='Tipo Documento',
       default='CUIT',
       help='TipoDocumento - Tipo de documento del cliente')
    
    x_softys_numero_documento = fields.Char(
        string='Número Documento',
        compute='_compute_numero_documento',
        store=True,
        help='NumeroDocumento - CUIT/DNI sin guiones'
    )
    
    x_softys_tipo_contribuyente = fields.Selection([
        ('CF', 'Consumidor Final'),
        ('RI', 'Responsable Inscripto'),
        ('EX', 'Exento'),
        ('MT', 'Monotributista'),
        ('RS', 'Responsable Simplificado'),
        ('NR', 'No Responsable'),
    ], string='Tipo Contribuyente',
       default='CF',
       help='TipoContribuyente - CF/RI/EX/MT según AFIP')
    
    # Canal y Subcanal
    x_softys_actividad = fields.Char(
        string='Actividad YAS',
        help='Actividad comercial original de YAS (para mapping)'
    )
    
    x_softys_canal_id = fields.Many2one(
        'softys.canal',
        string='Canal Nextbyn',
        help='CodigoCanal - Canal comercial del cliente'
    )
    
    x_softys_subcanal_id = fields.Many2one(
        'softys.subcanal',
        string='Subcanal Nextbyn',
        help='CodigoSubcanal - Subcanal comercial del cliente'
    )
    
    # Dirección
    x_softys_calle = fields.Char(
        string='Calle',
        help='Calle - Nombre de la calle'
    )
    
    x_softys_numero = fields.Char(
        string='Número',
        help='Numero - Altura de la calle'
    )
    
    x_softys_localidad = fields.Char(
        string='Localidad Nextbyn',
        help='Localidad - Barrio o localidad'
    )
    
    x_softys_provincia = fields.Char(
        string='Provincia Nextbyn',
        help='Provincia - Provincia o estado'
    )
    
    x_softys_codigo_postal = fields.Char(
        string='Código Postal Nextbyn',
        help='CodigoPostal - Código postal'
    )
    
    # Geolocalización
    x_softys_latitud = fields.Float(
        string='Latitud',
        digits=(10, 6),
        help='Latitud - Coordenada geográfica'
    )
    
    x_softys_longitud = fields.Float(
        string='Longitud',
        digits=(10, 6),
        help='Longitud - Coordenada geográfica'
    )
    
    # Contacto
    x_softys_telefono = fields.Char(
        string='Teléfono Nextbyn',
        help='Telefono - Número de teléfono'
    )
    
    x_softys_email = fields.Char(
        string='Email Nextbyn',
        help='Email - Correo electrónico'
    )
    
    # Comercial
    x_softys_condicion_venta = fields.Selection([
        ('CON', 'Contado'),
        ('CTA', 'Cuenta Corriente'),
        ('CHE', 'Cheque'),
        ('TRJ', 'Tarjeta'),
    ], string='Condición de Venta',
       default='CON',
       help='CodigoCondicionVenta - Forma de pago habitual')
    
    x_softys_lista_precio = fields.Char(
        string='Lista de Precio',
        help='CodigoListaPrecio - Código de lista de precios'
    )
    
    # Estado
    x_softys_anulado = fields.Boolean(
        string='Anulado',
        default=False,
        help='Anulado - SI si el cliente está inactivo'
    )
    
    x_softys_exportar = fields.Boolean(
        string='Exportar a Nextbyn',
        default=True,
        help='Indica si este cliente se exporta a Nextbyn'
    )
    
    # === CAMPOS PARA CLIENTESRUTA ===
    
    x_softys_codigo_ruta = fields.Integer(
        string='Código Ruta',
        help='Código de la ruta asignada al cliente'
    )
    
    x_softys_dia_visita = fields.Selection([
        ('LUN', 'Lunes'),
        ('MAR', 'Martes'),
        ('MIE', 'Miércoles'),
        ('JUE', 'Jueves'),
        ('VIE', 'Viernes'),
        ('SAB', 'Sábado'),
        ('DOM', 'Domingo'),
    ], string='Día de Visita',
       help='Día de la semana para visita del vendedor')
    
    x_softys_secuencia = fields.Integer(
        string='Secuencia Visita',
        default=0,
        help='Orden de visita dentro de la ruta (OrdenDeVisita)'
    )
    
    @api.depends('x_softys_idcliente', 'vat')
    def _compute_softys_codigo(self):
        """Calcula el código del cliente para Nextbyn."""
        for partner in self:
            if partner.vat:
                # Usar CUIT/DNI sin guiones ni espacios
                cuit = partner.vat.replace('-', '').replace(' ', '')
                partner.x_softys_codigo = cuit
            elif partner.x_softys_idcliente:
                partner.x_softys_codigo = str(partner.x_softys_idcliente)
            else:
                partner.x_softys_codigo = str(partner.id)
    
    @api.depends('name')
    def _compute_razon_social(self):
        """Calcula la razón social desde el nombre."""
        for partner in self:
            partner.x_softys_razon_social = partner.name or ''
    
    @api.depends('vat')
    def _compute_numero_documento(self):
        """Calcula el número de documento sin guiones."""
        for partner in self:
            if partner.vat:
                partner.x_softys_numero_documento = partner.vat.replace('-', '').replace(' ', '')
            else:
                partner.x_softys_numero_documento = ''
