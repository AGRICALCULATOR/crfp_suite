import uuid
from odoo import models, fields, api


class CrfpFieldBuyer(models.Model):
    _name = 'crfp.field.buyer'
    _description = 'Field Buyer Access'
    _order = 'name'

    name = fields.Char(
        string='Name',
        required=True,
        help='Name of the field buyer (e.g., "Juan — Turrialba")',
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Contact',
        help='Optional link to an Odoo contact for email notifications',
    )
    token = fields.Char(
        string='Access Token',
        readonly=True,
        copy=False,
        index=True,
        default=lambda self: uuid.uuid4().hex[:16],
    )
    active = fields.Boolean(default=True)
    last_accessed = fields.Datetime(
        string='Last Accessed',
        readonly=True,
    )
    access_count = fields.Integer(
        string='Views',
        readonly=True,
        default=0,
    )
    notes = fields.Text(string='Notes')
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
    )

    # ── Computed Link ─────────────────────────────────────────
    portal_url = fields.Char(
        string='Price Link',
        compute='_compute_portal_url',
    )

    def _compute_portal_url(self):
        base = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for rec in self:
            rec.portal_url = f'{base}/crfp/prices/{rec.token}'

    def action_regenerate_token(self):
        """Generate a new access token."""
        self.ensure_one()
        self.token = uuid.uuid4().hex[:16]
        return True

    def action_copy_link(self):
        """Return action that displays a notification with the link for easy copy."""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Link del Comprador',
                'message': self.portal_url,
                'type': 'info',
                'sticky': True,
            },
        }

    def action_open_portal_preview(self):
        """Open the field buyer portal in a new browser tab for preview."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': self.portal_url,
            'target': 'new',
        }

    def _register_access(self):
        """Called by the portal controller to log access."""
        self.sudo().write({
            'last_accessed': fields.Datetime.now(),
            'access_count': self.access_count + 1,
        })
