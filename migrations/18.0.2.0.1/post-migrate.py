# -*- coding: utf-8 -*-
"""
Migración post-actualización:
El campo softys.export.file.datas pasó de attachment=True a attachment=False.
Los archivos generados con la versión anterior quedaron en ir.attachment.
Esta migración copia el contenido de los attachments al campo del modelo.
"""

import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    ExportFile = env['softys.export.file']
    Attachment = env['ir.attachment']

    files = ExportFile.search([])
    _logger.info(
        'Migrando %s archivos softys.export.file desde ir.attachment',
        len(files)
    )
    migrated = 0
    skipped = 0

    for export_file in files:
        attachment = Attachment.search([
            ('res_model', '=', 'softys.export.file'),
            ('res_id', '=', export_file.id),
            ('res_field', '=', 'datas'),
        ], limit=1)

        if attachment and attachment.datas:
            export_file.datas = attachment.datas
            migrated += 1
        else:
            skipped += 1

    _logger.info(
        'Migración finalizada: %s archivos migrados, %s sin attachment.',
        migrated, skipped
    )
