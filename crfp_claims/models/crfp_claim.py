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

    # ── Send Claim Email ──
    def action_send_claim_email(self):
        """Open email composer with formal legal claim letter."""
        self.ensure_one()
        ship = self.shipment_id
        recipient = self.responsible_partner_id or self.partner_id

        # Build claim type label
        type_labels = dict(self._fields['claim_type'].selection)
        claim_type_label = type_labels.get(self.claim_type, self.claim_type)

        # Build shipment details
        ship_details = ''
        if ship:
            ship_details = (
                f'<li><strong>Shipment Reference:</strong> {ship.name}</li>'
                f'<li><strong>Bill of Lading / Booking:</strong> {ship.booking_id.booking_reference if ship.booking_id else "N/A"}</li>'
                f'<li><strong>Vessel / Voyage:</strong> {ship.vessel_name or "N/A"} / {ship.voyage_number or "N/A"}</li>'
                f'<li><strong>Container Number:</strong> {ship.container_ids[0].container_number if ship.container_ids else "N/A"}</li>'
                f'<li><strong>Port of Origin:</strong> {ship.port_origin_id.name if ship.port_origin_id else "N/A"}</li>'
                f'<li><strong>Port of Destination:</strong> {ship.port_destination_id.name if ship.port_destination_id else "N/A"}</li>'
                f'<li><strong>ETD:</strong> {ship.etd or "N/A"}</li>'
                f'<li><strong>ETA:</strong> {ship.eta or "N/A"}</li>'
            )

        # Build evidence list
        evidence_list = ''
        if self.evidence_ids:
            for ev in self.evidence_ids:
                evidence_list += f'<li>{ev.name} ({dict(ev._fields["evidence_type"].selection).get(ev.evidence_type, "")})</li>'

        # Currency
        currency = self.currency_id.name if self.currency_id else 'USD'

        subject = f'FORMAL CARGO CLAIM — {self.name} — {claim_type_label} — {ship.name if ship else ""}'

        body = f'''
<p style="font-family: Arial, sans-serif; font-size: 13px;">
<strong style="font-size: 15px;">FORMAL NOTICE OF CARGO CLAIM</strong><br/>
<em>Under the Hague-Visby Rules / COGSA — Carriage of Goods by Sea Act</em>
</p>

<p><strong>Date:</strong> {fields.Date.today()}<br/>
<strong>Claim Reference:</strong> {self.name}<br/>
<strong>Claim Type:</strong> {claim_type_label}</p>

<p><strong>From:</strong><br/>
CR FARM PRODUCTS VYM Y M SOCIEDAD ANONIMA<br/>
Tax ID: 3-101-808635<br/>
Costa Rica</p>

<p><strong>To:</strong><br/>
{recipient.name if recipient else "—"}</p>

<hr/>

<p>Dear Sir/Madam,</p>

<p>We hereby formally notify you of our claim for <strong>{claim_type_label.lower()}</strong>
in connection with the following shipment:</p>

<p><strong>SHIPMENT DETAILS:</strong></p>
<ul>{ship_details}</ul>

<p><strong>DESCRIPTION OF CLAIM:</strong></p>
<div style="background: #f9f9f9; padding: 10px; border-left: 3px solid #c00; margin: 10px 0;">
{self.description or "See attached documentation."}
</div>

<p><strong>CLAIMED AMOUNT:</strong> {currency} {self.claimed_amount:,.2f}</p>

<p>This amount represents the value of the damaged/lost/delayed cargo as evidenced
by the commercial invoice and supporting documentation.</p>

{"<p><strong>SUPPORTING EVIDENCE:</strong></p><ul>" + evidence_list + "</ul>" if evidence_list else ""}

<p><strong>LEGAL BASIS:</strong></p>
<p>This claim is submitted pursuant to the applicable international conventions governing
the carriage of goods by sea, including but not limited to the Hague-Visby Rules and/or
the Carriage of Goods by Sea Act (COGSA). We reserve all our rights under these
conventions and applicable law.</p>

<p><strong>REQUESTED ACTION:</strong></p>
<p>We formally request:</p>
<ol>
<li>Acknowledgment of receipt of this claim within 7 business days</li>
<li>A formal written response addressing liability within 30 days</li>
<li>Full compensation of {currency} {self.claimed_amount:,.2f} for the damages described above</li>
</ol>

<p><strong>PRESERVATION OF EVIDENCE:</strong></p>
<p>All damaged goods and packaging have been preserved for inspection.
We are available to arrange a joint survey at your earliest convenience.</p>

<p>Please direct all correspondence regarding this claim to the undersigned.</p>

<p>Sincerely,<br/><br/>
<strong>CR FARM PRODUCTS VYM S.A.</strong><br/>
Export Department<br/>
Claim Reference: {self.name}
</p>

<hr/>
<p style="font-size: 10px; color: #888;">
<em>This notice constitutes a formal claim under international maritime law.
Failure to respond within the specified timeframe may result in further legal action.
All rights reserved.</em>
</p>
'''

        # Collect evidence attachments
        attachment_ids = []
        for ev in self.evidence_ids:
            if ev.attachment_ids:
                attachment_ids.extend(ev.attachment_ids.ids)

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mail.compose.message',
            'views': [[False, 'form']],
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_model': 'crfp.claim',
                'default_res_ids': [self.id],
                'default_partner_ids': [recipient.id] if recipient else [],
                'default_subject': subject,
                'default_body': body,
                'default_attachment_ids': attachment_ids,
                'default_composition_mode': 'comment',
            },
        }

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
