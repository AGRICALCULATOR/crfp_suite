from odoo import models, fields, api


class CrfpFreightQuote(models.Model):
    _name = 'crfp.freight.quote'
    _description = 'Freight Quote from Carrier/Forwarder'
    _order = 'valid_until desc, id desc'
    _inherit = ['mail.thread']

    name = fields.Char(string='Reference', help='Quote reference, e.g. Q2026-184')

    # Carrier from Odoo contacts (res.partner), not from crfp.carrier
    carrier_partner_id = fields.Many2one(
        'res.partner', string='Carrier / Forwarder',
        help='Select the carrier or forwarder from Odoo contacts')
    carrier_name = fields.Char(
        related='carrier_partner_id.name', store=True, string='Carrier Name')

    # DEPRECATED (Sprint 0): carrier_id will be removed in v2.0.
    # Use carrier_partner_id (res.partner) instead.
    # Kept for backward compat with existing data only.
    carrier_id = fields.Many2one('crfp.carrier', string='Legacy Carrier (deprecated)')

    port_id = fields.Many2one('crfp.port', string='Destination Port', required=True)
    container_type_id = fields.Many2one('crfp.container.type', string='Container Type')
    delivery_type = fields.Selection([
        ('port-port', 'Port to Port'),
        ('door-port', 'Door to Port'),
        ('port-door', 'Port to Door'),
        ('door-door', 'Door to Door'),
    ], string='Delivery Type', default='port-port')

    all_in_freight = fields.Float(string='All-in Freight (USD)', required=True,
                                  tracking=True,
                                  help='Total freight: BAS+BAF+THC+all surcharges')
    transit_days = fields.Integer(string='Transit Days')
    routing = fields.Selection([
        ('direct', 'Direct'),
        ('transship', 'Transshipment'),
    ], string='Routing', default='direct')
    transship_port = fields.Char(string='Transshipment Port')

    valid_from = fields.Date(string='Valid From')
    valid_until = fields.Date(string='Valid Until')
    source = fields.Char(string='Source', help='Email reference, agent name, etc.')

    # What is included in the quoted freight
    inc_transport = fields.Boolean(string='Includes Internal Transport')
    inc_thc_origin = fields.Boolean(string='Includes THC Origin')
    inc_broker = fields.Boolean(string='Includes Customs Broker CR')
    inc_thc_dest = fields.Boolean(string='Includes THC Destination')
    inc_inland_dest = fields.Boolean(string='Includes Inland Delivery Dest.')
    inc_fumig_dest = fields.Boolean(string='Includes Fumigation Dest.')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('expired', 'Expired'),
    ], string='Status', default='draft', tracking=True)

    active = fields.Boolean(default=True)
    notes = fields.Text(string='Notes')

    @api.depends('valid_until')
    def _compute_is_expired(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.is_expired = rec.valid_until and rec.valid_until < today

    is_expired = fields.Boolean(compute='_compute_is_expired')

    def action_activate(self):
        self.write({'state': 'active'})

    def action_expire(self):
        self.write({'state': 'expired'})

    @api.model
    def _cron_auto_expire(self):
        """Scheduled action: mark expired quotes."""
        today = fields.Date.context_today(self)
        expired = self.search([
            ('state', '=', 'active'),
            ('valid_until', '<', today),
        ])
        if expired:
            expired.write({'state': 'expired'})

    def action_request_update(self):
        """Open email composer to request updated quote from carrier."""
        self.ensure_one()
        if not self.carrier_partner_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mail.compose.message',
            'views': [[False, 'form']],
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_model': 'crfp.freight.quote',
                'default_res_ids': self.ids,
                'default_partner_ids': [self.carrier_partner_id.id],
                'default_subject': f'Request Updated Freight Quote — {self.name or ""}',
                'default_body': f'<p>Dear {self.carrier_partner_id.name},</p>'
                    f'<p>We would like to request an updated freight quotation for:</p>'
                    f'<ul><li>Destination: {self.port_id.name or ""}</li>'
                    f'<li>Container: {self.container_type_id.name or "40ft HC Reefer"}</li>'
                    f'<li>Previous rate: ${self.all_in_freight:.2f}</li></ul>'
                    f'<p>Please send us your current rates.</p>'
                    f'<p>Best regards,<br/>CR Farm Products</p>',
                'default_composition_mode': 'comment',
            },
        }
