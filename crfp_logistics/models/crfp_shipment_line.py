from odoo import models, fields, api


class CrfpShipmentLine(models.Model):
    _name = 'crfp.shipment.line'
    _description = 'Shipment Line \u2014 Planned vs Actual'
    _order = 'sequence, id'

    shipment_id = fields.Many2one('crfp.shipment', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)

    # \u2500\u2500 References (M2O only, no modifications) \u2500\u2500
    sale_order_line_id = fields.Many2one('sale.order.line', string='SO Line')
    product_id = fields.Many2one('product.product', string='Odoo Product')
    crfp_product_id = fields.Many2one('crfp.product', string='CR Farm Product')
    container_id = fields.Many2one(
        'crfp.shipment.container', string='Container',
        domain="[('shipment_id', '=', parent.id)]")
    box_type_id = fields.Many2one('crfp.box.type', string='Box Type')

    # \u2500\u2500 Planned (copied from sale.order) \u2500\u2500
    boxes_planned = fields.Integer(string='Boxes Planned')
    pallets_planned = fields.Integer(string='Pallets Planned')
    boxes_per_pallet_planned = fields.Integer(string='Boxes/Plt Planned', default=66)
    net_weight_planned = fields.Float(string='Net Weight Planned (kg)', digits=(12, 2))
    gross_weight_planned = fields.Float(string='Gross Weight Planned (kg)', digits=(12, 2))
    price_unit_planned = fields.Float(string='Price/Box Planned (USD)', digits=(12, 2))

    # \u2500\u2500 Actual (operator fills after packing) \u2500\u2500
    boxes_actual = fields.Integer(string='Boxes Actual')
    pallets_actual = fields.Integer(string='Pallets Actual')
    boxes_per_pallet_actual = fields.Integer(string='Boxes/Plt Actual', default=66)
    net_weight_actual = fields.Float(string='Net Weight Actual (kg)', digits=(12, 2))
    gross_weight_actual = fields.Float(string='Gross Weight Actual (kg)', digits=(12, 2))

    # \u2500\u2500 Differences (computed) \u2500\u2500
    boxes_diff = fields.Integer(
        string='Box Diff', compute='_compute_diffs', store=True)
    weight_diff = fields.Float(
        string='Weight Diff (kg)', compute='_compute_diffs', store=True, digits=(12, 2))
    has_shortage = fields.Boolean(
        string='Shortage', compute='_compute_diffs', store=True)

    # \u2500\u2500 Shortage reason \u2500\u2500
    shortage_reason = fields.Selection([
        ('quality', 'Quality Issue'),
        ('availability', 'Not Available'),
        ('damage', 'Damaged'),
        ('weather', 'Weather'),
        ('client_request', 'Client Request'),
        ('other', 'Other'),
    ], string='Shortage Reason')
    shortage_notes = fields.Text(string='Shortage Notes')

    # \u2500\u2500 Traceability \u2500\u2500
    lot_number = fields.Char(string='Lot / Batch')
    production_date = fields.Date(string='Production Date')
    temperature_set = fields.Float(
        string='Temperature (\u00b0C)',
        help='Required temperature for this product')

    @api.depends('boxes_planned', 'boxes_actual',
                 'net_weight_planned', 'net_weight_actual')
    def _compute_diffs(self):
        for rec in self:
            rec.boxes_diff = rec.boxes_actual - rec.boxes_planned
            rec.weight_diff = rec.net_weight_actual - rec.net_weight_planned
            rec.has_shortage = rec.boxes_actual < rec.boxes_planned and rec.boxes_actual > 0

    @api.onchange('boxes_planned', 'crfp_product_id')
    def _onchange_recalc_planned_weight(self):
        """Recalculate planned weights when boxes or product change."""
        if self.boxes_planned and self.crfp_product_id:
            net_kg = self.crfp_product_id.net_kg or 0
            self.net_weight_planned = self.boxes_planned * net_kg
            self.gross_weight_planned = self.boxes_planned * net_kg * 1.05

    @api.onchange('boxes_actual', 'crfp_product_id')
    def _onchange_recalc_actual_weight(self):
        """Recalculate actual weights when actual boxes change."""
        if self.boxes_actual and self.crfp_product_id:
            net_kg = self.crfp_product_id.net_kg or 0
            self.net_weight_actual = self.boxes_actual * net_kg
            self.gross_weight_actual = self.boxes_actual * net_kg * 1.05

    @api.onchange('boxes_planned', 'boxes_per_pallet_planned')
    def _onchange_recalc_pallets(self):
        """Auto-calculate pallets from boxes and boxes_per_pallet."""
        if self.boxes_planned and self.boxes_per_pallet_planned:
            import math
            self.pallets_planned = math.ceil(
                self.boxes_planned / self.boxes_per_pallet_planned)
