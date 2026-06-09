# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SoftysExportMapping(models.Model):
    """
    Define las tablas de conversión (ValueMappers del .ktr).
    Convierte valores de Odoo/YAS a valores esperados por Softys.
    
    Ejemplos del .ktr:
    - iva_tipo → TipoContribuyente (RI→MON, EX→EXE, etc.)
    - Tipo → Mult (NC→-1, ND→1, FA→1, etc.)
    - CondiciondeVenta → CodigoCondicionVenta (CON→1, CTA→2, etc.)
    - canal_softys_tmp → canal_softys (1→01, 2→02, etc.)
    """
    _name = 'softys.export.mapping'
    _description = 'Mapping de Valores Softys'
    _order = 'mapping_type, sequence'
    
    name = fields.Char(
        string='Nombre',
        required=True,
        help='Nombre descriptivo del mapping'
    )
    
    mapping_type = fields.Selection([
        ('tipo_contribuyente', 'Tipo Contribuyente (IVA)'),
        ('multiplicador', 'Multiplicador (Tipo Comprobante)'),
        ('condicion_venta', 'Condición de Venta'),
        ('canal_codigo', 'Código Canal (formato)'),
        ('subcanal_codigo', 'Código Subcanal (formato)'),
        ('tipo_cliente', 'Tipo Cliente YAS→Softys'),
        ('cargo_vendedor', 'Cargo Personal Comercial'),
        ('estado_anulado', 'Estado Anulado'),
        ('custom', 'Personalizado'),
    ], string='Tipo Mapping', required=True, index=True)
    
    sequence = fields.Integer(
        string='Secuencia',
        default=10
    )
    
    active = fields.Boolean(
        string='Activo',
        default=True
    )
    
    description = fields.Text(
        string='Descripción',
        help='Descripción del propósito de este mapping'
    )
    
    # Relación con items
    item_ids = fields.One2many(
        'softys.export.mapping.item',
        'mapping_id',
        string='Items de Conversión'
    )
    
    item_count = fields.Integer(
        string='Total Items',
        compute='_compute_item_count',
        store=True
    )
    
    default_value = fields.Char(
        string='Valor por Defecto',
        help='Valor a retornar si no se encuentra match en los items'
    )
    
    @api.depends('item_ids')
    def _compute_item_count(self):
        for record in self:
            record.item_count = len(record.item_ids)
    
    def map_value(self, source_value):
        """
        Convierte un valor de origen a valor de destino según el mapping.
        
        Args:
            source_value: Valor a convertir
            
        Returns:
            str: Valor convertido, o default_value si no hay match
        """
        self.ensure_one()
        
        if not source_value:
            return self.default_value or ''
        
        # Buscar match exacto
        item = self.item_ids.filtered(
            lambda i: i.source_value == str(source_value)
        )
        
        if item:
            return item[0].target_value or ''
        
        # Si no hay match, retornar default
        return self.default_value or ''
    
    def map_values_dict(self):
        """
        Retorna un diccionario de conversión {source: target}
        para uso eficiente en loops.
        """
        self.ensure_one()
        return {
            item.source_value: item.target_value 
            for item in self.item_ids
        }


class SoftysExportMappingItem(models.Model):
    """
    Item individual de un mapping (un par source→target).
    Equivalente a cada línea en los ValueMappers del .ktr
    """
    _name = 'softys.export.mapping.item'
    _description = 'Item de Mapping Softys'
    _order = 'mapping_id, sequence, source_value'
    
    mapping_id = fields.Many2one(
        'softys.export.mapping',
        string='Mapping',
        required=True,
        ondelete='cascade',
        index=True
    )
    
    sequence = fields.Integer(
        string='Secuencia',
        default=10
    )
    
    source_value = fields.Char(
        string='Valor Origen',
        required=True,
        help='Valor en sistema origen (Odoo/YAS)'
    )
    
    target_value = fields.Char(
        string='Valor Destino',
        required=True,
        help='Valor en sistema destino (Softys)'
    )
    
    description = fields.Char(
        string='Descripción',
        help='Descripción opcional del significado'
    )
    
    _sql_constraints = [
        ('unique_source_per_mapping',
         'UNIQUE(mapping_id, source_value)',
         'El valor de origen debe ser único dentro del mismo mapping.')
    ]


class SoftysClienteMapping(models.Model):
    """
    Mappings específicos de clientes (código YAS → código Softys).
    Del JavaScript: CodigoCliente YAS → diferentes valores según IdCliente.
    
    Ejemplos del .ktr:
    - IdCliente=3656 → '001971-036-001'
    - IdCliente=3838 → '001971-036-008'
    - IdCliente=4142 → '001971-037-001'
    - etc.
    """
    _name = 'softys.cliente.mapping'
    _description = 'Mapping Código Cliente Softys'
    _order = 'partner_id'
    
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        required=True,
        domain=[('customer_rank', '>', 0)],
        help='Cliente en Odoo (corresponde a IdCliente en YAS)'
    )
    
    yas_idcliente = fields.Integer(
        string='ID Cliente YAS',
        help='ID original del cliente en YAS (referencia)'
    )
    
    softys_codigo = fields.Char(
        string='Código Softys',
        required=True,
        help='Código del cliente en formato Softys (ej: 001971-036-001)'
    )
    
    active = fields.Boolean(
        string='Activo',
        default=True
    )
    
    notes = fields.Text(
        string='Notas'
    )
    
    _sql_constraints = [
        ('unique_partner',
         'UNIQUE(partner_id)',
         'Ya existe un mapping para este cliente.')
    ]


class SoftysCanalMapping(models.Model):
    """
    Mappings de Actividad → Canal/Subcanal (las 88 reglas del JavaScript).
    
    Del .ktr JavaScript masivo:
    - if (actividad=='KIOSCO') { canal='01'; subcanal='07'; }
    - if (actividad=='RESTAURANTE') { canal='01'; subcanal='09'; }
    - etc... (88 condiciones)
    """
    _name = 'softys.canal.mapping'
    _description = 'Mapping Actividad → Canal/Subcanal'
    _order = 'actividad'
    
    actividad = fields.Char(
        string='Actividad',
        required=True,
        help='Actividad del cliente (campo de YAS/Odoo)'
    )
    
    canal_id = fields.Many2one(
        'softys.canal',
        string='Canal',
        required=True,
        help='Canal Softys asignado'
    )
    
    subcanal_id = fields.Many2one(
        'softys.subcanal',
        string='Subcanal',
        required=True,
        help='Subcanal Softys asignado'
    )
    
    active = fields.Boolean(
        string='Activo',
        default=True
    )
    
    notes = fields.Text(
        string='Notas'
    )
    
    _sql_constraints = [
        ('unique_actividad',
         'UNIQUE(actividad)',
         'Ya existe un mapping para esta actividad.')
    ]
    
    @api.model
    def get_canal_subcanal(self, actividad):
        """
        Obtiene canal y subcanal según actividad.
        
        Args:
            actividad: String con la actividad del cliente
            
        Returns:
            tuple: (codigo_canal, codigo_subcanal) o (None, None)
        """
        if not actividad:
            return (None, None)
        
        mapping = self.search([
            ('actividad', '=', actividad.strip().upper()),
            ('active', '=', True)
        ], limit=1)
        
        if mapping and mapping.canal_id and mapping.subcanal_id:
            return (
                mapping.canal_id.codigo,
                mapping.subcanal_id.codigo
            )
        
        return (None, None)
