from odoo import models, fields, api


class CrfpPalletConfig(models.Model):
    _name = 'crfp.pallet.config'
    _description = 'Pallet Configuration (Boxes per Pallet)'
    _order = 'product_keyword, weight_kg'
    _rec_name = 'product_keyword'

    product_keyword = fields.Char(
        string='Product Keyword', required=True,
        help='Keyword to match product name, e.g. YUCA VALENCIA')
    weight_kg = fields.Float(
        string='Weight (kg)', required=True,
        help='Net weight of the box in kg')
    boxes_per_pallet = fields.Integer(
        string='Boxes per Pallet', required=True, default=66)
    active = fields.Boolean(default=True)
    notes = fields.Text(string='Notes')

    @api.depends('product_keyword', 'weight_kg', 'boxes_per_pallet')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s \u2014 %gkg \u2014 %d boxes' % (
                rec.product_keyword or 'N/A',
                rec.weight_kg or 0,
                rec.boxes_per_pallet or 0,
            )
