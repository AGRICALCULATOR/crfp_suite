from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Stub for l10n_cr view compatibility (field removed/missing in Odoo 19)
    hacienda_rate_auto_update = fields.Boolean(
        string="Actualizar tipo de cambio automáticamente (Hacienda)",
        config_parameter="l10n_cr.hacienda_rate_auto_update",
    )
