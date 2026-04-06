from odoo import models, fields, api


class CrfpContainerConfigLine(models.Model):
    _name = 'crfp.container.config.line'
    _description = 'Container Configuration Product Line'
    _order = 'sequence, id'

    config_id = fields.Many2one(
        'crfp.container.config',
        string='Container Config',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(default=10)

    product_id = fields.Many2one(
        'product.product',
        string='Product',
        ondelete='restrict',
    )
    pallet_config_id = fields.Many2one(
        'crfp.pallet.config',
        string='Pallet Config',
        ondelete='set null',
        help='Auto-fills boxes/pallet and net weight per box',
    )
    num_pallets = fields.Integer(string='Pallets', default=1, required=True)
    boxes_per_pallet = fields.Integer(string='Boxes/Pallet', default=66, required=True)
    net_weight_per_box_kg = fields.Float(
        string='Net Weight/Box (kg)', digits=(12, 3),
        help='Net weight of product per box in kg',
    )
    gross_weight_per_box_kg = fields.Float(
        string='Gross Weight/Box (kg)', digits=(12, 3),
        help='Gross weight (net + packaging tare) per box in kg',
    )

    # ── Computed totals per line ──
    total_boxes = fields.Integer(
        string='Total Boxes', compute='_compute_totals', store=True,
    )
    total_net_weight_kg = fields.Float(
        string='Total Net (kg)', compute='_compute_totals', store=True, digits=(12, 2),
    )
    total_gross_weight_kg = fields.Float(
        string='Total Gross (kg)', compute='_compute_totals', store=True, digits=(12, 2),
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Compute
    # ─────────────────────────────────────────────────────────────────────────

    @api.depends('num_pallets', 'boxes_per_pallet',
                 'net_weight_per_box_kg', 'gross_weight_per_box_kg')
    def _compute_totals(self):
        for rec in self:
            boxes = (rec.num_pallets or 0) * (rec.boxes_per_pallet or 0)
            rec.total_boxes = boxes
            rec.total_net_weight_kg = boxes * (rec.net_weight_per_box_kg or 0.0)
            rec.total_gross_weight_kg = boxes * (rec.gross_weight_per_box_kg or 0.0)

    # ─────────────────────────────────────────────────────────────────────────
    # Onchange
    # ─────────────────────────────────────────────────────────────────────────

    @api.onchange('pallet_config_id')
    def _onchange_pallet_config_id(self):
        if self.pallet_config_id:
            self.boxes_per_pallet = self.pallet_config_id.boxes_per_pallet
            self.net_weight_per_box_kg = self.pallet_config_id.weight_kg
