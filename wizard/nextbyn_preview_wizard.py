# -*- coding: utf-8 -*-
"""
Wizard para preview de exportación Nextbyn.
"""

import base64
from odoo import models, fields, api


class NextbynPreviewWizard(models.TransientModel):
    """Wizard para mostrar preview de datos a exportar"""
    _name = 'nextbyn.preview.wizard'
    _description = 'Preview Exportación Nextbyn'
    
    entity_id = fields.Many2one(
        'nextbyn.export.entity',
        string='Entidad',
        readonly=True
    )
    
    preview_text = fields.Text(
        string='Vista Previa',
        readonly=True
    )
    
    record_count = fields.Integer(
        string='Registros',
        readonly=True
    )
    
    csv_file = fields.Binary(
        string='Archivo CSV',
        readonly=True,
        attachment=False
    )
    
    csv_filename = fields.Char(
        string='Nombre Archivo',
        readonly=True
    )
    
    def action_download_csv(self):
        """Generar y descargar el CSV completo"""
        self.ensure_one()
        
        if not self.entity_id:
            return {'type': 'ir.actions.act_window_close'}
        
        # Generar el CSV completo (devuelve tupla: content, count)
        csv_content, record_count = self.entity_id._generate_csv_content()
        
        # Convertir a base64
        csv_base64 = base64.b64encode(csv_content.encode('utf-8'))
        
        # Actualizar campos
        filename = f"{self.entity_id.name}_{fields.Datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        self.write({
            'csv_file': csv_base64,
            'csv_filename': filename,
        })
        
        # Retornar acción de descarga
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content?model={self._name}&id={self.id}&field=csv_file&filename_field=csv_filename&download=true',
            'target': 'new',
        }
