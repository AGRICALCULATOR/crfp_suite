from odoo import models, fields


class CrfpPalletConfig(models.Model):
    _name = 'crfp.pallet.config'
    _description = 'Pallet Configuration (Boxes per Pallet)'
    _order = 'product_keyword, weight_kg'

    product_keyword = fields.Char(string='Product Keyword', required=True,
                                  help='Keyword to match product name, e.g. YUCA VALENCIA')
    weight_kg = fields.Float(string='Weight (kg)', required=True,
                             help='Net weight of the box in kg')
    boxes_per_pallet = fields.Integer(string='Boxes per Pallet', required=True,
                                      default=66)
    active = fields.Boolean(default=True)
    notes = fields.Text(string='Notes')
