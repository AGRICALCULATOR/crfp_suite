from odoo import models, fields, api


class CrfpPriceHistory(models.Model):
    _name = 'crfp.price.history'
    _description = 'Raw Material Price History'
    _order = 'date desc, crfp_product_id'

    crfp_product_id = fields.Many2one('crfp.product', string='Product',
                                       required=True, ondelete='cascade',
                                       index=True)
    date = fields.Date(string='Date', required=True, default=fields.Date.today,
                       index=True)
    price_crc = fields.Float(string='Price (CRC)', required=True, digits=(12, 2))
    exchange_rate = fields.Float(string='Exchange Rate', digits=(12, 2))
    price_usd = fields.Float(string='Price (USD)', compute='_compute_price_usd',
                             store=True, digits=(12, 4))

    _sql_constraints = [
        ('product_date_unique',
         'UNIQUE(crfp_product_id, date)',
         'Only one price entry per product per day.'),
    ]

    @api.depends('price_crc', 'exchange_rate')
    def _compute_price_usd(self):
        for rec in self:
            if rec.exchange_rate:
                rec.price_usd = rec.price_crc / rec.exchange_rate
            else:
                rec.price_usd = 0.0

    @api.model
    def record_prices(self, quotation):
        """Record today's prices from a quotation's lines."""
        today = fields.Date.context_today(self)
        for line in quotation.line_ids:
            existing = self.search([
                ('crfp_product_id', '=', line.crfp_product_id.id),
                ('date', '=', today),
            ], limit=1)
            vals = {
                'crfp_product_id': line.crfp_product_id.id,
                'date': today,
                'price_crc': line.raw_price_crc,
                'exchange_rate': quotation.exchange_rate,
            }
            if existing:
                existing.write(vals)
            else:
                self.create(vals)
