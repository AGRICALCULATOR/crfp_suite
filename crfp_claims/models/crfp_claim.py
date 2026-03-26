from odoo import models, fields, api
from odoo.exceptions import UserError


class CrfpClaim(models.Model):
    _name = 'crfp.claim'
    _description = 'Export Claim'
    _order = 'create_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Claim Ref', readonly=True, default='New', copy=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('investigation', 'Investigation'),
        ('response_pending', 'Response Pending'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, index=True)

    # Type and origin
    claim_type = fields.Selection([
        ('quality', 'Quality Issue'),
        ('temperature', 'Temperature Issue'),
        ('shortage', 'Shortage / Missing'),
        ('delay', 'Delay'),
        ('damage', 'Damage'),
        ('documentation', 'Documentation Issue'),
        ('other', 'Other'),
    ], string='Claim Type', required=True, tracking=True)

    origin = fields.Selection([
        ('customer', 'Customer Claim (they claim to us)'),
        ('internal', 'Internal Claim (we claim to third party)'),
    ], string='Origin', required=True, default='customer', tracking=True)

    description = fields.Html(string='Description')
    date_filed = fields.Date(string='Date Filed', default=fields.Date.today)
    date_closed = fields.Date(string='Date Closed')

    # Relations to shipment
    shipment_id = fields.Many2one('crfp.shipment', string='Shipment', tracking=True)
    container_id = fields.Many2one('crfp.shipment.container', string='Container')
    shipment_line_ids = fields.Many2many('crfp.shipment.line', string='Affected Lines')
    sale_order_id = fields.Many2one('sale.order', string='Sale Order')

    # Parties
    partner_id = fields.Many2one('res.partner', string='Claimant / Recipient',
                                  tracking=True,
                                  help='Customer who claims (if customer origin) or party we claim to (if internal)')
    responsible_party = fields.Selection([
        ('carrier', 'Carrier / Naviera'),
        ('forwarder', 'Forwarder'),
        ('supplier', 'Supplier'),
        ('warehouse', 'Warehouse'),
        ('crfarm', 'CR Farm (internal)'),
        ('insurance', 'Insurance'),
        ('other', 'Other'),
    ], string='Responsible Party', tracking=True)
    responsible_partner_id = fields.Many2one('res.partner', string='Responsible Company')

    # Amounts
    claimed_amount = fields.Float(string='Claimed Amount', digits=(12, 2), tracking=True)
    approved_amount = fields.Float(string='Approved Amount', digits=(12, 2), tracking=True)
    recovered_amount = fields.Float(string='Recovered Amount', digits=(12, 2), tracking=True)
    currency_id = fields.Many2one('res.currency', string='Currency',
                                   default=lambda self: self.env.ref('base.USD', raise_if_not_found=False))

    # Resolution
    resolution_type = fields.Selection([
        ('credit_note', 'Credit Note'),
        ('replacement', 'Replacement Shipment'),
        ('discount', 'Discount on Next Order'),
        ('insurance_recovery', 'Insurance Recovery'),
        ('absorbed', 'Absorbed by CR Farm'),
        ('rejected', 'Claim Rejected'),
        ('other', 'Other'),
    ], string='Resolution Type', tracking=True)
    resolution_notes = fields.Text(string='Resolution Notes')
    credit_note_id = fields.Many2one('account.move', string='Credit Note')

    # Management
    assigned_to = fields.Many2one('res.users', string='Assigned To',
                                   default=lambda self: self.env.user, tracking=True)
    priority = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ], string='Priority', default='medium', tracking=True)
    deadline = fields.Date(string='Deadline')

    # O2M
    evidence_ids = fields.One2many('crfp.claim.evidence', 'claim_id', string='Evidence')
    log_ids = fields.One2many('crfp.claim.log', 'claim_id', string='Communication Log')

    # Computed
    evidence_count = fields.Integer(compute='_compute_evidence_count')

    @api.depends('evidence_ids')
    def _compute_evidence_count(self):
        for rec in self:
            rec.evidence_count = len(rec.evidence_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('crfp.claim') or 'New'
        return super().create(vals_list)

    # Auto-fill from shipment
    @api.onchange('shipment_id')
    def _onchange_shipment_id(self):
        if not self.shipment_id:
            return
        ship = self.shipment_id
        self.partner_id = ship.partner_id
        self.sale_order_id = ship.sale_order_id
        if ship.container_ids:
            self.container_id = ship.container_ids[0]

    # State transitions
    def action_open(self):
        for rec in self:
            rec.write({'state': 'open'})

    def action_investigate(self):
        for rec in self:
            rec.write({'state': 'investigation'})

    def action_response_pending(self):
        for rec in self:
            rec.write({'state': 'response_pending'})

    def action_resolve(self):
        for rec in self:
            if not rec.resolution_type:
                raise UserError('Please select a Resolution Type before resolving.')
            rec.write({'state': 'resolved'})

    def action_close(self):
        for rec in self:
            rec.write({'state': 'closed', 'date_closed': fields.Date.today()})

    def action_cancel(self):
        for rec in self:
            rec.write({'state': 'cancelled'})

    # Navigation
    def action_view_shipment(self):
        self.ensure_one()
        if not self.shipment_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'crfp.shipment',
            'res_id': self.shipment_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
