from odoo import models, fields, api


class CrfpFreightQuote(models.Model):
    _name = 'crfp.freight.quote'
    _description = 'Freight Quote from Carrier/Forwarder'
    _order = 'valid_until desc, id desc'
    _inherit = ['mail.thread']

    name = fields.Char(string='Reference', help='Quote reference, e.g. Q2026-184')
    carrier_id = fields.Many2one('crfp.carrier', string='Carrier / Forwarder',
                                 required=True)
    carrier_name = fields.Char(related='carrier_id.name', store=True)
    port_id = fields.Many2one('crfp.port', string='Destination Port',
                              required=True)
    container_type_id = fields.Many2one('crfp.container.type',
                                        string='Container Type')
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
    source = fields.Char(string='Source',
                         help='Email reference, agent name, etc.')

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
