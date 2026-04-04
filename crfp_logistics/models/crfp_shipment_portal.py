"""
crfp.shipment — portal notification extension.

Sends email to the client partner when shipment reaches
key states: shipped, arrived, delivered.
"""
import logging
from odoo import models, fields

_logger = logging.getLogger(__name__)

_NOTIFY_STATES = {'shipped', 'arrived', 'delivered'}

_TEMPLATE_REFS = {
    'shipped':   'crfp_logistics.email_template_shipment_shipped',
    'arrived':   'crfp_logistics.email_template_shipment_arrived',
    'delivered': 'crfp_logistics.email_template_shipment_delivered',
}


class CrfpShipmentPortal(models.Model):
    _inherit = 'crfp.shipment'

    # ── Portal URL helper ────────────────────────────────────────────────────

    def get_portal_url(self):
        self.ensure_one()
        base = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
        return f'{base}/my/crfarm-shipments/{self.id}'

    # ── State-change notifications ───────────────────────────────────────────

    def write(self, vals):
        if 'state' not in vals:
            return super().write(vals)

        # Record state before write for comparison
        state_before = {rec.id: rec.state for rec in self}
        result = super().write(vals)

        new_state = vals['state']
        if new_state in _NOTIFY_STATES:
            for rec in self:
                if state_before.get(rec.id) != new_state:
                    rec._notify_client_state_change(new_state)

        return result

    def _notify_client_state_change(self, new_state):
        """Send notification email to client partner on key state transitions."""
        self.ensure_one()
        if not self.partner_id or not self.partner_id.email:
            _logger.debug(
                'crfp_logistics: skipping notification for %s — no partner email', self.name)
            return

        template_ref = _TEMPLATE_REFS.get(new_state)
        if not template_ref:
            return

        try:
            template = self.env.ref(template_ref, raise_if_not_found=False)
            if template:
                base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
                template.with_context(base_url=base_url).send_mail(
                    self.id, force_send=True, raise_exception=False)
                _logger.info(
                    'crfp_logistics: sent "%s" notification to %s for shipment %s',
                    new_state, self.partner_id.email, self.name)
        except Exception:
            _logger.exception(
                'crfp_logistics: failed to send state notification for %s', self.name)
