import base64
from odoo import models, fields, api
from odoo.exceptions import UserError


class CrfpQuotation(models.Model):
    _name = 'crfp.quotation'
    _description = 'Export Price Quotation'
    _order = 'create_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Quotation Name', required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('sent', 'Sent'),
        ('won', 'Won (SO Created)'),
        ('lost', 'Lost'),
    ], string='Status', default='draft', tracking=True)

    # Commercial
    partner_id = fields.Many2one('res.partner', string='Client')
    client_type = fields.Selection([
        ('distribuidor', 'Distributor'),
        ('mayorista', 'Wholesaler'),
        ('retailer', 'Retailer'),
        ('directo', 'Direct'),
    ], string='Client Type', default='distribuidor')

    # Global parameters
    exchange_rate = fields.Float(string='Exchange Rate (CRC/USD)',
                                 default=503.0, digits=(12, 2), required=True)
    incoterm = fields.Selection([
        ('EXW', 'EXW'), ('FCA', 'FCA'), ('FOB', 'FOB'),
        ('CFR', 'CFR'), ('CIF', 'CIF'), ('CPT', 'CPT'),
        ('CIP', 'CIP'), ('DAP', 'DAP'), ('DDP', 'DDP'),
    ], string='Incoterm', default='FOB', required=True)

    # Logistics
    freight_quote_id = fields.Many2one('crfp.freight.quote', string='Active Freight Quote')
    port_id = fields.Many2one('crfp.port', string='Destination Port')
    container_type_id = fields.Many2one('crfp.container.type', string='Container Type')
    total_boxes = fields.Integer(string='Total Boxes in Container', default=1386)

    # Shipment info
    etd = fields.Date(string='ETD')
    eta = fields.Date(string='ETA')
    vessel_name = fields.Char(string='Vessel / Voyage')
    shipping_company = fields.Char(string='Shipping Company')

    # Fixed cost snapshot
    fc_transport = fields.Float(default=600.0)
    fc_thc_origin = fields.Float(default=380.0)
    fc_fumigation = fields.Float(default=180.0)
    fc_broker = fields.Float(default=150.0)
    fc_thc_dest = fields.Float(default=0.0)
    fc_fumig_dest = fields.Float(default=0.0)
    fc_inland_dest = fields.Float(default=0.0)
    fc_insurance_pct = fields.Float(default=0.30)
    fc_duties_pct = fields.Float(default=0.0)

    # Lines
    line_ids = fields.One2many('crfp.quotation.line', 'quotation_id', string='Product Lines')

    # Sale order link
    sale_order_id = fields.Many2one('sale.order', string='Sale Order', readonly=True, copy=False)

    # Computed
    line_count = fields.Integer(compute='_compute_line_count')
    total_amount = fields.Float(compute='_compute_totals', string='Total $/box')
    total_pallets = fields.Integer(compute='_compute_totals', string='Total Pallets')
    total_boxes_sum = fields.Integer(compute='_compute_totals', string='Total Boxes')
    total_order_amount = fields.Float(compute='_compute_totals', string='Total Order Amount')

    @api.depends('line_ids')
    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)

    @api.depends('line_ids.final_price', 'line_ids.include_in_pdf',
                 'line_ids.pallets', 'line_ids.boxes_per_pallet', 'line_ids.line_total')
    def _compute_totals(self):
        for rec in self:
            included = rec.line_ids.filtered(lambda l: l.include_in_pdf)
            rec.total_amount = sum(l.final_price for l in included)
            rec.total_pallets = sum(l.pallets for l in included)
            rec.total_boxes_sum = sum(l.total_boxes for l in included)
            rec.total_order_amount = sum(l.line_total for l in included)

    # ── Actions ──

    def action_create_sale_order(self):
        """Create a sale.order from this quotation."""
        self.ensure_one()
        if not self.partner_id:
            raise UserError('Please select a client before creating a Sale Order.')

        order_lines = []
        for line in self.line_ids.filtered('include_in_pdf'):
            if line.pallets <= 0:
                continue
            # Use line-level SKU first, fallback to base product link
            product = line.product_id or line.crfp_product_id.product_id
            if not product:
                raise UserError(
                    f'Product "{line.crfp_product_id.name}" has no Odoo SKU linked. '
                    f'Open the quotation, click on the line, and select the Odoo SKU.'
                )
            qty = line.pallets * line.boxes_per_pallet
            order_lines.append((0, 0, {
                'product_id': product.id,
                'product_uom_qty': qty,
                'price_unit': line.final_price,
                'name': (f"{line.crfp_product_id.name} — "
                         f"{line.pallets} pallets × {line.boxes_per_pallet} boxes/pallet"),
            }))

        if not order_lines:
            raise UserError('No product lines with pallets > 0. Enter pallet quantities first.')

        note_parts = [f"Incoterm: {self.incoterm}"]
        if self.port_id:
            note_parts.append(f"Port: {self.port_id.name}")
        if self.vessel_name:
            note_parts.append(f"Vessel: {self.vessel_name}")
        if self.etd:
            note_parts.append(f"ETD: {self.etd}")
        if self.eta:
            note_parts.append(f"ETA: {self.eta}")

        so_vals = {
            'partner_id': self.partner_id.id,
            'order_line': order_lines,
            'note': ' | '.join(note_parts),
        }
        if self.etd:
            so_vals['commitment_date'] = self.etd

        so = self.env['sale.order'].create(so_vals)
        self.write({'sale_order_id': so.id, 'state': 'won'})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': so.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_download_pdf(self):
        """Download the quotation as PDF."""
        self.ensure_one()
        return self.env.ref('crfp_pricing.action_report_crfp_quotation').report_action(self)

    def action_send_email(self):
        """Generate PDF, attach it, and open email composer."""
        self.ensure_one()
        if not self.partner_id:
            raise UserError('Please select a client before sending an email.')

        # Generate the PDF
        report = self.env.ref('crfp_pricing.action_report_crfp_quotation')
        pdf_content, _ = report._render_qweb_pdf(report.report_name, self.ids)

        # Create attachment
        attachment = self.env['ir.attachment'].create({
            'name': f'CRFP-Quotation-{self.name}.pdf',
            'type': 'binary',
            'datas': base64.b64encode(pdf_content),
            'res_model': 'crfp.quotation',
            'res_id': self.id,
            'mimetype': 'application/pdf',
        })

        # Build email body
        port_name = self.port_id.name if self.port_id else '—'
        body = (
            f'<p>Dear {self.partner_id.name or "Customer"},</p>'
            f'<p>Please find attached our export price quotation '
            f'<strong>{self.name}</strong>.</p>'
            f'<p>Incoterm: {self.incoterm}<br/>'
            f'Destination: {port_name}</p>'
            f'<p>Prices are valid for 7 days. Please let us know if you '
            f'have any questions or would like to confirm an order.</p>'
            f'<p>Best regards,<br/>'
            f'<strong>CR Farm Products VYM S.A</strong></p>'
        )

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mail.compose.message',
            'views': [[False, 'form']],
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_model': 'crfp.quotation',
                'default_res_ids': self.ids,
                'default_partner_ids': [self.partner_id.id],
                'default_subject': f'Export Price Quotation — {self.name}',
                'default_body': body,
                'default_attachment_ids': [attachment.id],
                'default_composition_mode': 'comment',
                'force_email': True,
            },
        }

    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_mark_sent(self):
        self.write({'state': 'sent'})

    def action_mark_lost(self):
        self.write({'state': 'lost'})
