# -*- coding: utf-8 -*-
"""
Transmisión SFTP de los 7 archivos al portal Nextbyn.

Reglas del instructivo V2.4.2 (Etapa 6) que condicionan este código:
  * Los 7 archivos van juntos pero sueltos: sin carpetas ni comprimir.
  * La transmisión es diaria y debe completarse antes de las 23:30.
  * Todo lo que entra por SFTP va directo al productivo de Nextbyn.
"""

import logging
import traceback

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    import paramiko
except ImportError:  # pragma: no cover
    paramiko = None


class SoftysConnector(models.Model):
    _inherit = 'softys.connector'

    # -------------------------------------------------------------------
    # Configuración de la conexión
    # -------------------------------------------------------------------
    sftp_enabled = fields.Boolean(
        string='Enviar por SFTP',
        default=False,
        help='Si está activo, cada exportación se transmite al portal Nextbyn. '
             'ATENCIÓN: lo que se sube por SFTP va directo al productivo de Nextbyn.'
    )

    sftp_host = fields.Char(
        string='Host SFTP',
        default='fileserver.nextbyn.com',
        help='Servidor SFTP provisto por Nextbyn'
    )

    sftp_port = fields.Integer(
        string='Puerto SFTP',
        default=2222
    )

    sftp_user = fields.Char(
        string='Usuario SFTP',
        help='Usuario provisto por Nextbyn (incluye el ID de empresa)'
    )

    sftp_password = fields.Char(
        string='Contraseña SFTP',
        help='Contraseña provista por Nextbyn'
    )

    sftp_path = fields.Char(
        string='Carpeta Remota',
        default='.',
        help='Carpeta destino en el servidor de Nextbyn. '
             'Por defecto el directorio inicial del usuario.'
    )

    sftp_timeout = fields.Integer(
        string='Timeout (seg)',
        default=60,
        help='Tiempo máximo de espera para conectar y transmitir'
    )

    # -------------------------------------------------------------------
    # Estado de la última transmisión
    # -------------------------------------------------------------------
    sftp_last_send = fields.Datetime(
        string='Última Transmisión',
        readonly=True
    )

    sftp_last_status = fields.Selection([
        ('success', 'Éxito'),
        ('failed', 'Fallida'),
    ], string='Estado Última Transmisión', readonly=True)

    sftp_last_message = fields.Text(
        string='Detalle Última Transmisión',
        readonly=True
    )

    # -------------------------------------------------------------------
    # Conexión
    # -------------------------------------------------------------------
    def _sftp_check_available(self):
        """La librería paramiko es una dependencia externa del módulo."""
        if paramiko is None:
            raise UserError(_(
                'La librería "paramiko" no está instalada en el servidor. '
                'Instalarla con: pip install paramiko'
            ))

    def _sftp_validate_config(self):
        self.ensure_one()
        faltan = [
            etiqueta
            for campo, etiqueta in [
                ('sftp_host', 'Host'),
                ('sftp_user', 'Usuario'),
                ('sftp_password', 'Contraseña'),
            ]
            if not self[campo]
        ]
        if faltan:
            raise UserError(_(
                'Falta completar la configuración SFTP: %s'
            ) % ', '.join(faltan))

    def _sftp_connect(self):
        """Abre la conexión. El llamador es responsable de cerrarla."""
        self.ensure_one()
        self._sftp_check_available()
        self._sftp_validate_config()

        transport = paramiko.Transport((self.sftp_host, self.sftp_port or 22))
        transport.banner_timeout = self.sftp_timeout or 60
        try:
            transport.connect(username=self.sftp_user, password=self.sftp_password)
            client = paramiko.SFTPClient.from_transport(transport)
            if client is None:
                raise UserError(_('No se pudo abrir el canal SFTP.'))
            client.get_channel().settimeout(self.sftp_timeout or 60)
        except Exception:
            transport.close()
            raise
        return transport, client

    def action_test_sftp_connection(self):
        """Prueba la conexión sin transmitir ningún archivo."""
        self.ensure_one()
        try:
            transport, client = self._sftp_connect()
        except UserError:
            raise
        except Exception as e:
            raise UserError(_('No se pudo conectar a %s:%s\n\n%s') % (
                self.sftp_host, self.sftp_port, e))

        try:
            destino = self.sftp_path or '.'
            client.chdir(destino)
            remoto = client.getcwd()
            cantidad = len(client.listdir('.'))
        except Exception as e:
            raise UserError(_(
                'Conectó correctamente pero no pudo acceder a la carpeta "%s".\n\n%s'
            ) % (self.sftp_path, e))
        finally:
            client.close()
            transport.close()

        raise UserError(_(
            'Conexión exitosa.\n\nServidor: %s:%s\nUsuario: %s\n'
            'Carpeta remota: %s\nArchivos en la carpeta: %s'
        ) % (self.sftp_host, self.sftp_port, self.sftp_user, remoto, cantidad))

    # -------------------------------------------------------------------
    # Transmisión
    # -------------------------------------------------------------------
    def send_files_sftp(self, files):
        """
        Sube los archivos al portal Nextbyn.

        `files` es una lista de tuplas (nombre, contenido en bytes).
        Los archivos van sueltos en la carpeta remota, sin comprimir,
        tal como exige el instructivo.

        Devuelve la lista de nombres transmitidos.
        """
        self.ensure_one()

        if not files:
            raise UserError(_('No hay archivos para transmitir.'))

        transport, client = self._sftp_connect()
        enviados = []
        try:
            if self.sftp_path and self.sftp_path != '.':
                client.chdir(self.sftp_path)

            for filename, content in files:
                # Se sube con nombre temporal y se renombra al final para que
                # Nextbyn nunca tome un archivo a medio escribir.
                tmp_name = '%s.tmp' % filename
                with client.open(tmp_name, 'wb') as remoto:
                    remoto.write(content)
                try:
                    client.remove(filename)
                except IOError:
                    pass  # no existía, es lo normal
                client.rename(tmp_name, filename)
                enviados.append(filename)
                _logger.info('Nextbyn SFTP: transmitido %s (%s bytes)',
                             filename, len(content))
        finally:
            client.close()
            transport.close()

        self.write({
            'sftp_last_send': fields.Datetime.now(),
            'sftp_last_status': 'success',
            'sftp_last_message': _('%s archivos transmitidos: %s') % (
                len(enviados), ', '.join(enviados)),
        })
        return enviados

    # -------------------------------------------------------------------
    # Envío diario automático
    # -------------------------------------------------------------------
    @api.model
    def cron_daily_send(self):
        """
        Corrida diaria: genera el lote del día y lo transmite a Nextbyn.

        Con days_back=15 el archivo Comprobantes queda con la venta del día
        y la de los 15 días anteriores, y StockFisico con la foto del día,
        que es lo que pide el instructivo para la transmisión diaria.
        """
        conectores = self.search([('active', '=', True), ('sftp_enabled', '=', True)])
        if not conectores:
            _logger.info('Nextbyn SFTP: no hay conectores con transmisión activa')
            return False

        for connector in conectores:
            company_code = connector.company_code

            # Cada conector va dentro de un savepoint. El scheduler es el dueño
            # de la transacción del cron, así que acá no se hace commit ni
            # rollback: hacerlo suelta el lock que Odoo toma sobre ir_cron y el
            # scheduler aborta la corrida entera (por eso el cron fallaba
            # mientras el mismo código andaba bien desde la interfaz).
            run = self.env['softys.export.run'].create({
                'connector_id': connector.id,
                'state': 'draft',
            })

            try:
                with self.env.cr.savepoint():
                    run.action_run_export()
            except Exception as e:
                # El savepoint deshizo lo que la exportación dejó a medias,
                # pero la corrida sigue viva: sobre ella se deja el detalle.
                _logger.exception(
                    'Nextbyn SFTP: falló la corrida diaria del conector %s',
                    company_code)
                self._registrar_fallo_corrida(run, connector, e)

        return True

    def _registrar_fallo_corrida(self, run, connector, error):
        """
        Deja asentado en la corrida y en el conector por qué falló el envío.

        Va en su propio savepoint: si registrar el fallo también fallara, el
        cron igual debe terminar y pasar al siguiente conector.
        """
        detalle = traceback.format_exc()
        resumen = str(error) or _('Error sin detalle')

        try:
            with self.env.cr.savepoint():
                run.write({
                    'state': 'failed',
                    'end_date': fields.Datetime.now(),
                    'sftp_state': 'failed',
                    'sftp_message': detalle,
                })
                run._log('error', _('Falló la corrida automática: %s') % resumen)
                connector.write({
                    'sftp_last_send': fields.Datetime.now(),
                    'sftp_last_status': 'failed',
                    'sftp_last_message': resumen,
                })
                run._notify_sftp_failure(detalle)
        except Exception:
            _logger.exception(
                'Nextbyn SFTP: no se pudo registrar el fallo de la corrida %s',
                run.id)

    def action_send_now(self):
        """Genera y transmite el lote en el momento, desde el conector."""
        self.ensure_one()
        self._sftp_check_available()
        self._sftp_validate_config()

        run = self.env['softys.export.run'].create({
            'connector_id': self.id,
            'state': 'draft',
        })
        run.action_run_export()

        return {
            'name': _('Transmisión Nextbyn'),
            'type': 'ir.actions.act_window',
            'res_model': 'softys.export.run',
            'res_id': run.id,
            'view_mode': 'form',
            'target': 'current',
        }
