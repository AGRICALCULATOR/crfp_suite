from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    hacienda_rate_auto_update = fields.Boolean(
        string='Actualizar tipos Hacienda automáticamente',
        default=True,
    )
    hacienda_rate_interval_number = fields.Integer(
        string='Intervalo de actualización (días)',
        default=1,
    )
    hacienda_rate_last_sync = fields.Datetime(
        string='Última sincronización Hacienda',
        readonly=True,
    )
