from odoo import models, fields, api
from odoo.exceptions import UserError


class CrfpQuotation(models.Model):
    _name = 'crfp.quotation'
    _description = 'Export Price Quotation'
    _order = 'create_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Quotation Name', required=True,
                       help='Client or descriptive name for this quotation')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('sent', 'Sent'),
        ('won', 'Won (SO Created)'),
        ('lost', 'Lost'),
    ], string='Status', default='draft', tracking=True)

    # Commercial
    partner_id = fields.Many2one('res.partner', string='Client',
                                 domain=[('customer_rank', '>', 0)])
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

    # Logistics reference
    freight_quote_id = fields.Many2one('crfp.freight.quote',
                                        string='Active Freight Quote')
    port_id = fields.Many2one('crfp.port', string='Destination Port')
    container_type_id = fields.Many2one('crfp.container.type',
                                        string='Container Type')
    total_boxes = fields.Integer(string='Total Boxes in Container',
                                 default=1386)

    # Shipment info
    etd = fields.Date(string='ETD')
    eta = fields.Date(string='ETA')
    vessel_name = fields.Char(string='Vessel / Voyage')
    shipping_company = fields.Char(string='Shipping Company')

    # Fixed cost snapshot (copied from crfp.fixed.cost at creation time)
    fc_transport = fields.Float(string='Transport (USD)', default=600.0)
    fc_thc_origin = fields.Float(string='THC Origin (USD)', default=380.0)
    fc_fumigation = fields.Float(string='Fumigation (USD)', default=180.0)
    fc_broker = fields.Float(string='Broker (USD)', default=150.0)
    fc_thc_dest = fields.Float(string='THC Dest (USD)', default=0.0)
    fc_fumig_dest = fields.Float(string='Fumig. Dest (USD)', default=0.0)
    fc_inland_dest = fields.Float(string='Inland Dest (USD)', default=0.0)
    fc_insurance_pct = fields.Float(string='Insurance %', default=0.30)
    fc_duties_pct = fields.Float(string='Duties %', default=0.0)

    # Lines
    line_ids = fields.One2many('crfp.quotation.line', 'quotation_id',
                               string='Product Lines')

    # Sale order link
    sale_order_id = fields.Many2one('sale.order', string='Sale Order',
                                     readonly=True, copy=False)

    # Computed
    line_count = fields.Integer(compute='_compute_line_count')
    total_amount = fields.Float(compute='_compute_totals', string='Total Amount')

    @api.depends('line_ids')
    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)

    @api.depends('line_ids.final_price', 'line_ids.include_in_pdf')
    def _compute_totals(self):
        for rec in self:
            rec.total_amount = sum(
                l.final_price for l in rec.line_ids if l.include_in_pdf
            )

    def action_create_sale_order(self):
        """Create a sale.order from this quotation using Odoo standard API."""
        self.ensure_one()
        if not self.partner_id:
            raise UserError('Please select a client before creating a Sale Order.')
        if not self.line_ids:
            raise UserError('No product lines in this quotation.')

        order_lines = []
        for line in self.line_ids:
            if not line.include_in_pdf:
                continue
            product = line.crfp_product_id.product_id
            if not product:
                raise UserError(
                    f'Product "{line.crfp_product_id.name}" has no Odoo product '
                    f'linked. Please configure it in Export Products.'
                )
            order_lines.append((0, 0, {
                'product_id': product.id,
                'product_uom_qty': line.pallets * line.boxes_per_pallet if line.pallets else 1,
                'price_unit': line.final_price,
                'name': f"{line.crfp_product_id.name} - "
                        f"{line.pallets or 0} pallets x "
                        f"{line.boxes_per_pallet or 0} boxes/pallet",
            }))

        if not order_lines:
            raise UserError('No lines with "Include in PDF" checked.')

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
        self.write({
            'sale_order_id': so.id,
            'state': 'won',
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': so.id,
            'view_mode': 'form',
            'target': 'current',
        }
