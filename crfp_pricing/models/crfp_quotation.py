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

    # Global parameters — defaults loaded from crfp.settings on creation
    exchange_rate = fields.Float(
        string='Exchange Rate (CRC/USD)', digits=(12, 2), required=True,
        help='Exchange rate at time of quotation (snapshot)',
    )
    incoterm = fields.Selection([
        ('EXW', 'EXW'), ('FCA', 'FCA'), ('FOB', 'FOB'),
        ('CFR', 'CFR'), ('CIF', 'CIF'), ('CPT', 'CPT'),
        ('CIP', 'CIP'), ('DAP', 'DAP'), ('DDP', 'DDP'),
    ], string='Incoterm', default='FOB', required=True)

    # Logistics
    freight_quote_id = fields.Many2one('crfp.freight.quote', string='Active Freight Quote')
    port_id = fields.Many2one('crfp.port', string='Destination Port')
    container_type_id = fields.Many2one('crfp.container.type', string='Container Type')
    total_boxes = fields.Integer(string='Total Boxes in Container')

    # Shipment info
    etd = fields.Date(string='ETD')
    eta = fields.Date(string='ETA')
    vessel_name = fields.Char(string='Vessel / Voyage')
    shipping_company = fields.Char(string='Shipping Company')

    # Fixed cost snapshot — editable per quotation, defaults loaded from crfp.settings
    fc_transport = fields.Float(string='Transport (USD)', digits=(12, 2))
    fc_thc_origin = fields.Float(string='THC Origin (USD)', digits=(12, 2))
    fc_fumigation = fields.Float(string='Fumigation Origin (USD)', digits=(12, 2))
    fc_broker = fields.Float(string='Broker / Customs (USD)', digits=(12, 2))
    fc_thc_dest = fields.Float(string='THC Destination (USD)', digits=(12, 2))
    fc_fumig_dest = fields.Float(string='Fumigation Destination (USD)', digits=(12, 2))
    fc_inland_dest = fields.Float(string='Inland Destination (USD)', digits=(12, 2))
    fc_insurance_pct = fields.Float(string='Insurance (%)', digits=(12, 2))
    fc_duties_pct = fields.Float(string='Duties (%)', digits=(12, 2))

    # Lines
    line_ids = fields.One2many('crfp.quotation.line', 'quotation_id', string='Product Lines')

    # Sale order link
    sale_order_id = fields.Many2one('sale.order', string='Sale Order', readonly=True, copy=False)

    # Price list link (set when published to portal)
    price_list_id = fields.Many2one(
        'crfp.price.list', string='Published Price List',
        readonly=True, copy=False,
        help='Price list generated from this quotation for the wholesaler portal',
    )

    # Computed
    line_count = fields.Integer(compute='_compute_line_count')
    total_amount = fields.Float(compute='_compute_totals', string='Total $/box')
    total_pallets = fields.Integer(compute='_compute_totals', string='Total Pallets')
    total_boxes_sum = fields.Integer(compute='_compute_totals', string='Total Boxes')
    total_order_amount = fields.Float(compute='_compute_totals', string='Total Order Amount')

    # ─────────────────────────────────────────────────────────────────────────
    # Defaults — read from crfp.settings so no hardcodes in Python
    # ─────────────────────────────────────────────────────────────────────────

    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        settings = self.env['crfp.settings'].get_settings()
        mapping = {
            'exchange_rate': settings.exchange_rate,
            'total_boxes': settings.default_total_boxes,
            'fc_transport': settings.fc_transport_default,
            'fc_thc_origin': settings.fc_thc_origin_default,
            'fc_fumigation': settings.fc_fumigation_default,
            'fc_broker': settings.fc_broker_default,
            'fc_thc_dest': settings.fc_thc_dest_default,
            'fc_fumig_dest': settings.fc_fumig_dest_default,
            'fc_inland_dest': settings.fc_inland_dest_default,
            'fc_insurance_pct': settings.fc_insurance_pct_default,
            'fc_duties_pct': settings.fc_duties_pct_default,
        }
        for field, value in mapping.items():
            if field in fields_list:
                defaults[field] = value
        return defaults

    # ─────────────────────────────────────────────────────────────────────────
    # Computed
    # ─────────────────────────────────────────────────────────────────────────

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

    # ─────────────────────────────────────────────────────────────────────────
    # Actions
    # ─────────────────────────────────────────────────────────────────────────

    def action_create_sale_order(self):
        """Create a sale.order from this quotation."""
        self.ensure_one()
        if not self.partner_id:
            raise UserError('Please select a client before creating a Sale Order.')

        # Build lines and track which quotation line maps to each SO line
        order_lines = []
        quotation_lines_with_pallets = []
        for line in self.line_ids.filtered('include_in_pdf'):
            if line.pallets <= 0:
                continue
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
                'discount': 0,
                'name': (f"{line.crfp_product_id.name} — "
                         f"{line.pallets} pallets × {line.boxes_per_pallet} boxes/pallet"),
            }))
            quotation_lines_with_pallets.append(line)

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

        # Force correct prices — match by position in the filtered list (1:1)
        for idx, q_line in enumerate(quotation_lines_with_pallets):
            if idx < len(so.order_line):
                so_line = so.order_line[idx]
                if abs(so_line.price_unit - q_line.final_price) > 0.01:
                    so_line.write({'price_unit': q_line.final_price})

        try:
            so.write({'crfp_quotation_id': self.id})
        except Exception:
            pass  # crfp_logistics may not be installed
        self.write({'sale_order_id': so.id, 'state': 'won'})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': so.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_publish_price_list(self):
        """
        Generate a crfp.price.list from the calculated prices in this quotation.

        - If a client is set: creates a personalized list (Scenario A).
        - If no client: creates a general list by country (Scenario B / portal).
        The calculator is the single source of truth for prices.
        """
        self.ensure_one()
        lines_to_publish = self.line_ids.filtered(
            lambda l: l.include_in_pdf and l.crfp_product_id and l.final_price > 0
        )
        if not lines_to_publish:
            raise UserError(
                'No product lines with a calculated price. '
                'Please complete the calculator before publishing.'
            )

        today = fields.Date.today()
        iso = today.isocalendar()
        week_num = iso[1]
        year = iso[0]

        # Auto-increment version if a list already exists for same client/week/year
        existing = self.env['crfp.price.list'].search([
            ('client_id', '=', self.partner_id.id if self.partner_id else False),
            ('week_number', '=', week_num),
            ('year', '=', year),
        ], order='version desc', limit=1)
        version = (existing.version + 1) if existing else 1

        usd = self.env['res.currency'].search([('name', '=', 'USD')], limit=1)

        price_list_lines = [(0, 0, {
            'product_id': line.crfp_product_id.id,
            'price': line.final_price,
            'currency_id': usd.id,
        }) for line in lines_to_publish]

        country_id = (
            self.partner_id.country_id.id
            if self.partner_id and self.partner_id.country_id else False
        )

        price_list = self.env['crfp.price.list'].create({
            'week_number': week_num,
            'year': year,
            'version': version,
            'client_id': self.partner_id.id if self.partner_id else False,
            'country_id': country_id,
            'line_ids': price_list_lines,
        })
        self.write({'price_list_id': price_list.id})

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'crfp.price.list',
            'res_id': price_list.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_shipment(self):
        """Open the linked Shipment (if crfp_logistics is installed)."""
        self.ensure_one()
        if not self.sale_order_id:
            return
        try:
            shipment = self.env['crfp.shipment'].search([
                ('sale_order_id', '=', self.sale_order_id.id)
            ], limit=1)
            if shipment:
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'crfp.shipment',
                    'res_id': shipment.id,
                    'view_mode': 'form',
                    'target': 'current',
                }
        except Exception:
            pass

    def action_view_price_list(self):
        """Open the published price list linked to this quotation."""
        self.ensure_one()
        if not self.price_list_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'crfp.price.list',
            'res_id': self.price_list_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_sale_order(self):
        """Open the linked Sale Order."""
        self.ensure_one()
        if not self.sale_order_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': self.sale_order_id.id,
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

        report = self.env.ref('crfp_pricing.action_report_crfp_quotation')
        pdf_content, _ = report._render_qweb_pdf(report.report_name, self.ids)

        attachment = self.env['ir.attachment'].create({
            'name': f'CRFP-Quotation-{self.name}.pdf',
            'type': 'binary',
            'datas': base64.b64encode(pdf_content),
            'res_model': 'crfp.quotation',
            'res_id': self.id,
            'mimetype': 'application/pdf',
        })

        port_name = self.port_id.name if self.port_id else '—'
        body = (
            f'<p>Dear {self.partner_id.name or "Customer"},</p>'
            f'<p>Please find attached our export price quotation '
            f'<strong>{self.name}</strong>.</p>'
            f'<p>Incoterm: {self.incoterm}<br/>'
            f'Destination: {port_name}</p>'
            f'<p>Prices are valid for {self.env["crfp.settings"].get_settings().price_validity_days} days. '
            f'Please let us know if you have any questions or would like to confirm an order.</p>'
            f'<p>Best regards,<br/><strong>CR Farm Products VYM S.A</strong></p>'
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

    # ─────────────────────────────────────────────────────────────────────────
    # BP-02: Recalculate draft lines when exchange rate changes
    # ─────────────────────────────────────────────────────────────────────────

    def write(self, vals):
        res = super().write(vals)
        # If exchange_rate changed, recalculate all draft lines
        if 'exchange_rate' in vals:
            for rec in self.filtered(lambda r: r.state == 'draft'):
                rec.line_ids._compute_all_prices()
        return res

    # ─────────────────────────────────────────────────────────────────────────
    # BP-07: Onchange freight_quote_id — copy costs and recalculate
    # ─────────────────────────────────────────────────────────────────────────

    @api.onchange('freight_quote_id')
    def _onchange_freight_quote(self):
        if self.state == 'draft' and self.line_ids:
            self.line_ids._compute_all_prices()

    # ─────────────────────────────────────────────────────────────────────────
    # BP-08: Onchange incoterm — recalculate with new incoterm matrix
    # ─────────────────────────────────────────────────────────────────────────

    @api.onchange('incoterm')
    def _onchange_incoterm(self):
        if self.state == 'draft' and self.line_ids:
            self.line_ids._compute_all_prices()

    # ─────────────────────────────────────────────────────────────────────────
    # State actions
    # ─────────────────────────────────────────────────────────────────────────

    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_mark_sent(self):
        self.write({'state': 'sent'})

    def action_mark_lost(self):
        self.write({'state': 'lost'})
