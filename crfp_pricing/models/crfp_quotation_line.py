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

    # Editable per-line parameters (user can override defaults)
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

    # Order config
    pallets = fields.Integer(string='Pallets', default=0)
    boxes_per_pallet = fields.Integer(string='Boxes/Pallet', default=66)
    include_in_pdf = fields.Boolean(string='Include', default=True)

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
