# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SoftysExportWizard(models.TransientModel):
    """
    Wizard para ejecutar exportación manual a Softys.
    """
    _name = 'softys.export.wizard'
    _description = 'Asistente Exportación Softys'
    
    connector_id = fields.Many2one(
        'softys.connector',
        string='Conector',
        required=True,
        default=lambda self: self._default_connector()
    )
    
    # Opciones de filtrado adicionales (opcionales)
    filter_clientes = fields.Boolean(
        string='Filtrar Clientes',
        default=False,
        help='Si se activa, solo exporta clientes seleccionados'
    )
    
    cliente_ids = fields.Many2many(
        'res.partner',
        string='Clientes',
        domain=[('customer_rank', '>', 0)]
    )
    
    filter_articulos = fields.Boolean(
        string='Filtrar Artículos',
        default=False,
        help='Si se activa, solo exporta artículos seleccionados'
    )
    
    articulo_ids = fields.Many2many(
        'product.product',
        string='Artículos'
    )
    
    # Opciones de qué exportar
    export_clientes = fields.Boolean(
        string='Exportar Clientes',
        default=True
    )
    
    export_articulos = fields.Boolean(
        string='Exportar Artículos',
        default=True
    )
    
    export_comprobantes = fields.Boolean(
        string='Exportar Comprobantes',
        default=True
    )
    
    export_personal = fields.Boolean(
        string='Exportar Personal Comercial',
        default=True
    )
    
    export_clientes_ruta = fields.Boolean(
        string='Exportar Clientes Ruta',
        default=True
    )
    
    export_rutas = fields.Boolean(
        string='Exportar Rutas de Venta',
        default=True
    )
    
    export_stock = fields.Boolean(
        string='Exportar Stock Físico',
        default=True
    )
    
    # Override de días hacia atrás para comprobantes
    override_days_back = fields.Boolean(
        string='Cambiar Días hacia Atrás',
        default=False
    )
    
    days_back = fields.Integer(
        string='Días hacia Atrás',
        default=98
    )
    
    @api.model
    def _default_connector(self):
        """Obtener conector por defecto"""
        connector_id = self.env.context.get('default_connector_id')
        if connector_id:
            return connector_id
        
        # Buscar primer conector activo
        connector = self.env['softys.connector'].search([
            ('active', '=', True)
        ], limit=1)
        
        return connector.id if connector else False
    
    def action_export(self):
        """Ejecutar la exportación"""
        self.ensure_one()
        
        if not self.connector_id:
            raise UserError(_('Debe seleccionar un conector.'))
        
        # Validar que al menos una opción esté seleccionada
        if not any([
            self.export_clientes,
            self.export_articulos,
            self.export_comprobantes,
            self.export_personal,
            self.export_clientes_ruta,
            self.export_rutas,
            self.export_stock,
        ]):
            raise UserError(_('Debe seleccionar al menos un tipo de archivo para exportar.'))
        
        # Crear registro de ejecución
        run = self.env['softys.export.run'].create({
            'connector_id': self.connector_id.id,
            'state': 'draft',
        })
        
        # Agregar filtros al contexto si existen
        context = {
            'export_clientes': self.export_clientes,
            'export_articulos': self.export_articulos,
            'export_comprobantes': self.export_comprobantes,
            'export_personal': self.export_personal,
            'export_clientes_ruta': self.export_clientes_ruta,
            'export_rutas': self.export_rutas,
            'export_stock': self.export_stock,
        }
        
        if self.filter_clientes and self.cliente_ids:
            context['filter_cliente_ids'] = self.cliente_ids.ids
        
        if self.filter_articulos and self.articulo_ids:
            context['filter_articulo_ids'] = self.articulo_ids.ids
        
        if self.override_days_back:
            context['days_back'] = self.days_back
        
        # Ejecutar exportación con contexto
        run.with_context(**context).action_run_export()
        
        # Retornar acción para ver el resultado
        return {
            'name': _('Resultado Exportación'),
            'type': 'ir.actions.act_window',
            'res_model': 'softys.export.run',
            'res_id': run.id,
            'view_mode': 'form',
            'target': 'current',
        }
