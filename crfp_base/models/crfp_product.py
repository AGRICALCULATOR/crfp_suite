import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class CrfpProduct(models.Model):
    _name = 'crfp.product'
    _description = 'CR Farm Export Product'
    _order = 'category, sequence, name'

    name = fields.Char(string='Product Name', required=True,
                       help='e.g. YUCA VALENCIA, EDDOES, GINGER')
    sequence = fields.Integer(default=10)
    category = fields.Selection([
        ('tubers', 'Tubers & Root Vegetables'),
        ('coconut', 'Coconut'),
        ('sugar_cane', 'Sugar Cane'),
        ('vegetables', 'Vegetables & Others'),
    ], string='Category', required=True, default='tubers')

    # Raw material price
    raw_price_crc = fields.Float(string='Raw Price (CRC)',
                                 help='Raw material price in Costa Rican colones')
    net_kg = fields.Float(string='Net Weight (kg)',
                          help='Net kilos per box')
    default_box_cost = fields.Float(string='Default Box Cost (USD)',
                                    help='Default box/packaging cost in USD')

    # Processing costs per kg (USD)
    labor_per_kg = fields.Float(string='Labor / kg (USD)',
                                digits=(12, 4))
    materials_per_kg = fields.Float(string='Materials / kg (USD)',
                                    digits=(12, 4))
    indirect_per_kg = fields.Float(string='Indirect / kg (USD)',
                                   digits=(12, 4))

    # Default profit
    default_profit = fields.Float(string='Default Profit (USD)',
                                  help='Default profit per box in USD')

    # Calculation type - determines formula variant
    calc_type = fields.Selection([
        ('standard', 'Standard (txk * kg + box)'),
        ('flat_no_box', 'Flat (txk only, no box)'),
        ('flat_plus_box', 'Flat (txk + box, no kg multiply)'),
        ('kg_no_box', 'Per kg (txk * kg, no box)'),
    ], string='Calculation Type', required=True, default='standard',
       help='Determines how packing cost is calculated')

    # Purchase formula type
    purchase_formula = fields.Selection([
        ('standard', 'Standard: (kg * price) / tc'),
        ('quintal', 'Quintal: (1 * kg / 46) * (price / tc)'),
    ], string='Purchase Formula', required=True, default='standard',
       help='Quintal formula used for YUCA, EDDOES, ISLENA, Malanga, BIG TARO')

    # Gross weight type
    gross_weight_type = fields.Selection([
        ('standard', 'Standard: kg * 2.2 + 2 lb tare'),
        ('no_tare', 'No tare: kg * 2.2'),
        ('zero', 'Zero (coconut)'),
    ], string='Gross Weight Type', required=True, default='standard')

    # Link to Odoo product
    product_id = fields.Many2one('product.product', string='Odoo Product',
                                 help='Link to product.product for sale orders')

    active = fields.Boolean(default=True)
    notes = fields.Text(string='Notes')

    @api.depends('labor_per_kg', 'materials_per_kg', 'indirect_per_kg')
    def _compute_total_cost_per_kg(self):
        for rec in self:
            rec.total_cost_per_kg = (
                rec.labor_per_kg + rec.materials_per_kg + rec.indirect_per_kg
            )

    total_cost_per_kg = fields.Float(
        string='Total Cost / kg',
        compute='_compute_total_cost_per_kg',
        store=True,
        digits=(12, 4),
    )

    def write(self, vals):
        """BP-04: When raw_price_crc changes, update draft quotation lines and notify."""
        res = super().write(vals)
        if 'raw_price_crc' in vals:
            lines = self.env['crfp.quotation.line'].search([
                ('crfp_product_id', 'in', self.ids),
                ('quotation_id.state', '=', 'draft'),
            ])
            if lines:
                lines.write({'raw_price_crc': vals['raw_price_crc']})
                lines._compute_all_prices()
        return res

    def _notify_field_price_update(self, buyer_name, saved_count, week, year):
        """Send inbox notification to configured users after field buyer saves prices."""
        try:
            settings = self.env['crfp.settings'].get_settings()
            notify_partners = settings.field_price_notify_partner_ids
            if not notify_partners:
                return
            self.env['res.partner'].message_notify(
                partner_ids=notify_partners.ids,
                subject='Precios de campo actualizados — Semana %d/%d' % (week, year),
                body=(
                    '<p><b>%s</b> actualizó %d precio(s) de campo para la semana %d/%d.</p>'
                    % (buyer_name, saved_count, week, year)
                ),
                subtype_xmlid='mail.mt_comment',
            )
        except Exception:
            _logger.exception('Failed to send field price update notification')
