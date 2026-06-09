# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ProductProduct(models.Model):
    """
    Extensión de product.product para campos específicos de integración Nextbyn.
    Según documentación oficial de Nextbyn.
    """
    _inherit = 'product.product'
    
    x_softys_idarticulo = fields.Integer(
        string='ID Artículo YAS',
        help='ID original del artículo en sistema YAS',
        copy=False
    )
    
    x_softys_codigo = fields.Char(
        string='Código Artículo',
        compute='_compute_softys_codigo',
        store=True,
        help='Código del artículo para Nextbyn (CodigoArticulo en CSV)'
    )
    
    # Campos según documentación Nextbyn - Articulos
    x_softys_unidades_bulto = fields.Integer(
        string='Unidades por Bulto',
        default=1,
        help='En cuántas unidades fracciona la distribuidora el producto'
    )
    
    x_softys_valor_umedida = fields.Float(
        string='Valor Unidad Medida',
        default=0,
        help='Convierte el bulto a otra unidad de medida (litros, kilos, etc.)'
    )
    
    x_softys_valor_umedida2 = fields.Float(
        string='Valor Unidad Medida 2',
        default=0,
        help='Valor en segunda unidad de medida'
    )
    
    x_softys_ean_unidad = fields.Char(
        string='EAN Unidad',
        help='Código de barra de las unidades sueltas'
    )
    
    x_softys_retornable = fields.Boolean(
        string='Retornable',
        default=False,
        help='Es un artículo retornable (bidones, envases, etc.)'
    )
    
    x_softys_activo_fijo = fields.Boolean(
        string='Activo Fijo',
        default=False,
        help='Es un activo fijo (equipos de frío, etc.)'
    )
    
    x_softys_fracciona = fields.Boolean(
        string='Fracciona',
        default=False,
        help='El artículo se puede fraccionar'
    )
    
    x_softys_unidad_minima = fields.Integer(
        string='Unidad Mínima Facturación',
        default=0,
        help='Venta mínima en caso de fraccionarse'
    )
    
    x_softys_factor_facturacion = fields.Integer(
        string='Factor Facturación',
        default=0,
        help='Factor de venta para fraccionamiento'
    )
    
    x_softys_pesable = fields.Boolean(
        string='Pesable',
        default=False,
        help='Se vende por unidad y peso'
    )
    
    x_softys_es_combo = fields.Boolean(
        string='Es Combo',
        default=False,
        help='El artículo es un combo de otros productos'
    )
    
    x_softys_producto = fields.Boolean(
        string='Producto Nextbyn',
        compute='_compute_softys_producto',
        store=True,
        help='Indica si este producto se exporta a Nextbyn'
    )
    
    @api.depends('default_code', 'x_softys_idarticulo')
    def _compute_softys_codigo(self):
        """Calcula el código del producto."""
        for product in self:
            if product.default_code:
                product.x_softys_codigo = product.default_code
            elif product.x_softys_idarticulo:
                product.x_softys_codigo = str(product.x_softys_idarticulo)
            else:
                product.x_softys_codigo = str(product.id)
    
    @api.depends('seller_ids', 'seller_ids.partner_id')
    def _compute_softys_producto(self):
        """Determina si el producto se exporta a Nextbyn."""
        for product in self:
            connector = self.env['softys.connector'].search([
                ('active', '=', True)
            ], limit=1)
            
            if connector and connector.softys_partner_id:
                has_softys = any(
                    seller.partner_id.id == connector.softys_partner_id.id
                    for seller in product.seller_ids
                )
                product.x_softys_producto = has_softys
            else:
                product.x_softys_producto = False


class ProductTemplate(models.Model):
    """
    Extensión de product.template para campos específicos de integración Softys.
    """
    _inherit = 'product.template'
    
    x_softys_idarticulo = fields.Integer(
        string='ID Artículo YAS',
        compute='_compute_softys_template_fields',
        inverse='_inverse_softys_idarticulo',
        help='ID original del artículo en sistema YAS'
    )
    
    x_softys_codigo = fields.Char(
        string='Código Artículo Softys',
        compute='_compute_softys_template_fields',
        help='Código del artículo para Softys'
    )
    
    x_softys_codigobarra = fields.Char(
        string='Código de Barras Softys',
        compute='_compute_softys_template_fields',
        inverse='_inverse_softys_codigobarra',
        help='Código de barras principal del producto'
    )
    
    x_softys_unidad_venta = fields.Char(
        string='Unidad de Venta',
        compute='_compute_softys_template_fields',
        inverse='_inverse_softys_unidad_venta',
        help='Unidad de medida de venta'
    )
    
    x_softys_anulado = fields.Selection([
        ('0', 'Activo'),
        ('1', 'Anulado'),
    ], string='Estado Softys',
       compute='_compute_softys_template_fields',
       inverse='_inverse_softys_anulado',
       help='Estado del artículo para Softys')
    
    x_softys_producto = fields.Boolean(
        string='Producto Softys',
        compute='_compute_softys_template_fields',
        help='Indica si este producto pertenece al proveedor Softys'
    )

    @api.depends('product_variant_ids', 'product_variant_ids.x_softys_idarticulo',
                 'product_variant_ids.x_softys_codigo', 'product_variant_ids.x_softys_producto')
    def _compute_softys_template_fields(self):
        """Computa los campos Softys desde la primera variante."""
        for template in self:
            variant = template.product_variant_ids[:1]
            if variant:
                template.x_softys_idarticulo = variant.x_softys_idarticulo
                template.x_softys_codigo = variant.x_softys_codigo
                template.x_softys_codigobarra = variant.barcode or ''
                template.x_softys_unidad_venta = variant.uom_id.name if variant.uom_id else ''
                template.x_softys_anulado = '1' if not variant.active else '0'
                template.x_softys_producto = variant.x_softys_producto
            else:
                template.x_softys_idarticulo = 0
                template.x_softys_codigo = ''
                template.x_softys_codigobarra = ''
                template.x_softys_unidad_venta = ''
                template.x_softys_anulado = '0'
                template.x_softys_producto = False

    def _inverse_softys_idarticulo(self):
        for template in self:
            if template.product_variant_ids:
                template.product_variant_ids[:1].x_softys_idarticulo = template.x_softys_idarticulo

    def _inverse_softys_codigobarra(self):
        for template in self:
            if template.product_variant_ids:
                template.product_variant_ids[:1].barcode = template.x_softys_codigobarra

    def _inverse_softys_unidad_venta(self):
        # Solo lectura, no se puede cambiar desde template
        pass

    def _inverse_softys_anulado(self):
        for template in self:
            if template.product_variant_ids:
                template.product_variant_ids[:1].active = template.x_softys_anulado != '1'
