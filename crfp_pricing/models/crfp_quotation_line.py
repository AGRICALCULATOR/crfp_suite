from odoo import models, fields, api


class CrfpQuotationLine(models.Model):
    _name = 'crfp.quotation.line'
    _description = 'Export Quotation Product Line'
    _order = 'sequence, id'

    quotation_id = fields.Many2one('crfp.quotation', string='Quotation',
                                    required=True, ondelete='cascade')
    crfp_product_id = fields.Many2one('crfp.product', string='Product',
                                       required=True)
    sequence = fields.Integer(related='crfp_product_id.sequence', store=True)

    # ★ SKU link — per line, not per product (one base product has many SKUs)
    product_id = fields.Many2one(
        'product.product', string='Odoo SKU',
        help='Select the specific Odoo product/variant for this line. '
             'Required to create a Sale Order.')

    # Editable per-line parameters
    raw_price_crc = fields.Float(string='Raw Price (CRC)', digits=(12, 2))
    net_kg = fields.Float(string='Net Kg')
    box_cost = fields.Float(string='Box Cost (USD)', digits=(12, 2))
    labor_per_kg = fields.Float(digits=(12, 4))
    materials_per_kg = fields.Float(digits=(12, 4))
    indirect_per_kg = fields.Float(digits=(12, 4))
    profit = fields.Float(string='Profit (USD)', digits=(12, 2))

    # Calculated results
    purchase_cost = fields.Float(string='Purchase Cost (USD)', digits=(12, 4))
    packing_cost = fields.Float(string='Packing Cost (USD)', digits=(12, 4))
    exw_price = fields.Float(string='EXW Price (USD)', digits=(12, 2))
    logistics_per_box = fields.Float(string='Logistics/Box (USD)', digits=(12, 4))
    final_price = fields.Float(string='Final Price (USD)', digits=(12, 2))
    gross_lbs = fields.Float(string='Gross Lbs', digits=(12, 1))
    gross_kg = fields.Float(string='Gross Kg', compute='_compute_gross_kg', store=True, digits=(12, 1))

    # Order / pallet config
    pallets = fields.Integer(string='Pallets', default=0)
    boxes_per_pallet = fields.Integer(string='Boxes/Pallet', default=66)
    include_in_pdf = fields.Boolean(string='Include', default=True)

    # Computed fields for quotation form
    total_boxes = fields.Integer(string='Total Boxes', compute='_compute_totals', store=True)
    pallet_price = fields.Float(string='Price/Pallet', compute='_compute_totals', store=True, digits=(12, 2))
    line_total = fields.Float(string='Line Total', compute='_compute_totals', store=True, digits=(12, 2))

    @api.depends('gross_lbs')
    def _compute_gross_kg(self):
        for rec in self:
            rec.gross_kg = rec.gross_lbs / 2.20462 if rec.gross_lbs else 0.0

    @api.depends('pallets', 'boxes_per_pallet', 'final_price')
    def _compute_totals(self):
        for rec in self:
            rec.total_boxes = rec.pallets * rec.boxes_per_pallet
            rec.pallet_price = rec.final_price * rec.boxes_per_pallet
            rec.line_total = rec.final_price * rec.total_boxes

    @api.onchange('crfp_product_id')
    def _onchange_product(self):
        if self.crfp_product_id:
            p = self.crfp_product_id
            self.raw_price_crc = p.raw_price_crc
            self.net_kg = p.net_kg
            self.box_cost = p.default_box_cost
            self.labor_per_kg = p.labor_per_kg
            self.materials_per_kg = p.materials_per_kg
            self.indirect_per_kg = p.indirect_per_kg
            self.profit = p.default_profit
            # Pre-fill SKU from base product if set
            if p.product_id:
                self.product_id = p.product_id.id
