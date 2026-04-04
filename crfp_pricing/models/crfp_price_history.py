from odoo import models, fields


class CrfpPriceHistory(models.Model):
    _name = 'crfp.price.history'
    _description = 'Weekly Price History'
    _order = 'year desc, week desc, product_id'

    product_id = fields.Many2one('crfp.product', string='Product', required=True, index=True)
    week = fields.Integer(string='Week', required=True)
    year = fields.Integer(string='Year', required=True)
    version = fields.Integer(string='Version', default=1)
    client_id = fields.Many2one('res.partner', string='Client')
    price_usd = fields.Float(string='Price (USD)', digits=(12, 4))
    price_local = fields.Float(string='Price (Local)', digits=(12, 4))
    currency_id = fields.Many2one('res.currency', string='Local Currency')
    source = fields.Selection([
        ('manual', 'Manual'),
        ('price_list', 'Price List'),
        ('import', 'Import'),
    ], string='Source', default='manual')
