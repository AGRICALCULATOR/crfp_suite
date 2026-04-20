from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    hacienda_rate_auto_update = fields.Boolean(
        string='Actualizar tipos Hacienda automáticamente',
        config_parameter='tipos_cambio_bccr.hacienda_rate_auto_update',
        default=True,
    )
    hacienda_rate_interval_number = fields.Integer(
        string='Intervalo de actualización (días)',
        config_parameter='tipos_cambio_bccr.hacienda_rate_interval_number',
        default=1,
    )
    hacienda_rate_last_sync = fields.Datetime(
        string='Última sincronización Hacienda',
        readonly=True,
        config_parameter='tipos_cambio_bccr.hacienda_rate_last_sync',
    )

    def set_values(self):
        res = super().set_values()
        cron = self.env.ref('tipos_cambio_bccr.ir_cron_update_hacienda_rates', raise_if_not_found=False)
        if cron:
            for settings in self:
                interval = settings.hacienda_rate_interval_number or 1
                cron.sudo().write({
                    'active': settings.hacienda_rate_auto_update,
                    'interval_number': max(1, interval),
                    'interval_type': 'days',
                })
                break
        return res

    def action_update_hacienda_rates_now(self):
        self.ensure_one()
        self.env['res.currency'].sudo()._update_hacienda_rates()
        return {'type': 'ir.actions.client', 'tag': 'reload'}
