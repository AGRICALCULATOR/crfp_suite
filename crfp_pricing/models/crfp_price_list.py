import logging
from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class CrfpPriceListLine(models.Model):
    _name = 'crfp.price.list.line'
    _description = 'Weekly Price List Line'
    _order = 'product_id'

    price_list_id = fields.Many2one(
        'crfp.price.list', string='Price List', required=True, ondelete='cascade')
    product_id = fields.Many2one('crfp.product', string='Product', required=True)
    price = fields.Float(string='Price', required=True, digits=(12, 4))
    currency_id = fields.Many2one('res.currency', string='Currency', required=True)


class CrfpPriceList(models.Model):
    _name = 'crfp.price.list'
    _description = 'Weekly Price List'
    _order = 'year desc, week_number desc, version desc'
    _rec_name = 'name'

    name = fields.Char(string='Name', compute='_compute_name', store=True)
    week_number = fields.Integer(string='Week Number', required=True)
    year = fields.Integer(string='Year', required=True)
    version = fields.Integer(string='Version', default=1)
    status = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('active', 'Active'),
        ('archived', 'Archived'),
    ], string='Status', default='draft', required=True, index=True)
    activation_date = fields.Date(string='Activation Date')
    country_id = fields.Many2one('res.country', string='Country')
    client_id = fields.Many2one('res.partner', string='Client')
    line_ids = fields.One2many('crfp.price.list.line', 'price_list_id', string='Price Lines')

    @api.depends('week_number', 'year', 'version')
    def _compute_name(self):
        for rec in self:
            rec.name = f'W{rec.week_number:02d}/{rec.year} v{rec.version}'

    def action_confirm(self):
        for rec in self:
            if rec.status != 'draft':
                raise UserError(f'Price list {rec.name} is not in Draft status.')
            rec.status = 'confirmed'

    def action_activate(self):
        for rec in self:
            if rec.status not in ('draft', 'confirmed'):
                raise UserError(f'Price list {rec.name} cannot be activated.')
            rec.write({'status': 'active', 'activation_date': fields.Date.today()})
            self._create_history_records(rec)

    def action_archive_list(self):
        for rec in self:
            rec.status = 'archived'

    def _create_history_records(self, price_list):
        History = self.env['crfp.price.history']
        for line in price_list.line_ids:
            History.create({
                'product_id': line.product_id.id,
                'week': price_list.week_number,
                'year': price_list.year,
                'version': price_list.version,
                'client_id': price_list.client_id.id if price_list.client_id else False,
                'price_usd': line.price if line.currency_id.name == 'USD' else 0.0,
                'price_local': line.price if line.currency_id.name != 'USD' else 0.0,
                'currency_id': line.currency_id.id,
                'source': 'price_list',
            })

    @api.model
    def action_auto_activate_prices(self):
        """Cron: activate confirmed price lists with activation_date <= today."""
        today = fields.Date.today()
        to_activate = self.search([
            ('status', '=', 'confirmed'),
            ('activation_date', '<=', today),
        ])
        for price_list in to_activate:
            try:
                price_list.action_activate()
                _logger.info('Auto-activated price list: %s', price_list.name)
            except Exception as e:
                _logger.error('Failed to auto-activate %s: %s', price_list.name, e)
