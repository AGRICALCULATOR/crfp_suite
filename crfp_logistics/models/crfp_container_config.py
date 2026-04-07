from odoo import models, fields, api
from odoo.exceptions import ValidationError


class CrfpContainerConfig(models.Model):
    _name = 'crfp.container.config'
    _description = 'Container Configuration'
    _order = 'date desc, id desc'
    _rec_name = 'name'

    # ── Identity ──
    name = fields.Char(
        string='Reference', compute='_compute_name', store=True,
        help='Auto-generated reference for this container configuration',
    )
    date = fields.Date(string='Date', default=fields.Date.today, required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
    ], string='Status', default='draft', required=True)

    # ── Links ──
    sale_order_id = fields.Many2one(
        'sale.order', string='Sales Order', ondelete='set null', index=True,
    )

    # ── Container setup ──
    container_type_id = fields.Many2one(
        'crfp.container.type', string='Container Type',
        required=True, ondelete='restrict',
    )
    capacity_boxes = fields.Integer(
        string='Container Capacity (boxes)',
        related='container_type_id.capacity_boxes', store=False,
        help='Standard box capacity of the selected container type',
    )

    # ── Mode: single-product vs. mixed ──
    is_mixed = fields.Boolean(
        string='Mixed Products', default=False,
        help='Enable to configure multiple products with different packaging in one container',
    )

    # ── Simple mode fields (single product) ──
    pallet_config_id = fields.Many2one(
        'crfp.pallet.config', string='Pallet Configuration',
        ondelete='set null',
        help='Select a pallet configuration to auto-fill boxes/pallet and weight',
    )
    box_type_id = fields.Many2one(
        'crfp.box.type', string='Box Type', ondelete='set null',
    )
    num_pallets = fields.Integer(
        string='Number of Pallets', default=20,
        help='Total pallets to load into the container',
    )
    boxes_per_pallet = fields.Integer(
        string='Boxes per Pallet', default=66,
        help='Number of boxes stacked on each pallet',
    )
    net_weight_per_box_kg = fields.Float(
        string='Net Weight / Box (kg)', digits=(12, 3),
        help='Net weight in kg of each box (auto-filled from Pallet Configuration)',
    )
    gross_weight_per_box_kg = fields.Float(
        string='Gross Weight / Box (kg)', digits=(12, 3),
        help='Gross weight per box (net product + box tare). Used in logistics documents.',
    )

    # ── Mixed mode: per-product lines ──
    product_line_ids = fields.One2many(
        'crfp.container.config.line', 'config_id', string='Product Lines',
    )

    # ── Computed totals (both modes) ──
    total_boxes = fields.Integer(
        string='Total Boxes', compute='_compute_totals', store=True,
    )
    total_weight_kg = fields.Float(
        string='Total Net Weight (kg)', compute='_compute_totals',
        store=True, digits=(12, 2),
    )
    total_gross_weight_kg = fields.Float(
        string='Total Gross Weight (kg)', compute='_compute_totals',
        store=True, digits=(12, 2),
        help='Total gross weight for logistics documents',
    )
    total_volume_m3 = fields.Float(
        string='Est. Volume (m³)', compute='_compute_totals',
        store=True, digits=(12, 3),
        help='Estimated volume based on standard box dimensions (0.048 m³/box)',
    )
    fill_rate_pct = fields.Float(
        string='Fill Rate (%)', compute='_compute_totals',
        store=True, digits=(12, 1),
        help='Percentage of container capacity used (total_boxes / capacity_boxes)',
    )

    # ── Notes ──
    notes = fields.Text(string='Notes')

    # ─────────────────────────────────────────────────────────────────────────
    # Compute methods
    # ─────────────────────────────────────────────────────────────────────────

    @api.depends('container_type_id', 'sale_order_id', 'date')
    def _compute_name(self):
        for rec in self:
            parts = []
            if rec.container_type_id:
                parts.append(rec.container_type_id.code or rec.container_type_id.name)
            if rec.sale_order_id:
                parts.append(rec.sale_order_id.name)
            if rec.date:
                parts.append(str(rec.date))
            rec.name = ' / '.join(parts) if parts else 'Container Config'

    @api.depends(
        'is_mixed',
        'num_pallets', 'boxes_per_pallet',
        'net_weight_per_box_kg', 'gross_weight_per_box_kg',
        'container_type_id.capacity_boxes',
        'product_line_ids.total_boxes',
        'product_line_ids.total_net_weight_kg',
        'product_line_ids.total_gross_weight_kg',
        'product_line_ids.num_pallets',
    )
    def _compute_totals(self):
        BOX_VOLUME_M3 = 0.048  # standard export box ~60×40×20 cm
        for rec in self:
            if rec.is_mixed:
                total_boxes = sum(rec.product_line_ids.mapped('total_boxes'))
                total_net = sum(rec.product_line_ids.mapped('total_net_weight_kg'))
                total_gross = sum(rec.product_line_ids.mapped('total_gross_weight_kg'))
                # Auto-sync num_pallets from lines in mixed mode
                rec.num_pallets = sum(rec.product_line_ids.mapped('num_pallets'))
            else:
                total_boxes = (rec.num_pallets or 0) * (rec.boxes_per_pallet or 0)
                total_net = total_boxes * (rec.net_weight_per_box_kg or 0.0)
                total_gross = total_boxes * (rec.gross_weight_per_box_kg or 0.0)

            rec.total_boxes = total_boxes
            rec.total_weight_kg = total_net
            rec.total_gross_weight_kg = total_gross
            rec.total_volume_m3 = total_boxes * BOX_VOLUME_M3

            capacity = rec.container_type_id.capacity_boxes if rec.container_type_id else 0
            rec.fill_rate_pct = (total_boxes / capacity * 100.0) if capacity and total_boxes else 0.0

    # ─────────────────────────────────────────────────────────────────────────
    # Constraints
    # ─────────────────────────────────────────────────────────────────────────

    @api.constrains('total_boxes', 'fill_rate_pct')
    def _check_capacity(self):
        for rec in self:
            if rec.fill_rate_pct > 105.0:
                raise ValidationError(
                    'Container "%s" exceeds capacity by %.1f%%. '
                    'Total boxes: %d, Capacity: %d. '
                    'Please reduce the number of boxes or pallets.'
                    % (rec.name, rec.fill_rate_pct, rec.total_boxes,
                       rec.capacity_boxes or 0)
                )

    # ─────────────────────────────────────────────────────────────────────────
    # Onchange
    # ─────────────────────────────────────────────────────────────────────────

    @api.onchange('pallet_config_id')
    def _onchange_pallet_config_id(self):
        if self.pallet_config_id:
            self.boxes_per_pallet = self.pallet_config_id.boxes_per_pallet
            self.net_weight_per_box_kg = self.pallet_config_id.weight_kg

    @api.onchange('total_boxes', 'capacity_boxes')
    def _onchange_warn_overcapacity(self):
        """Show a warning (not blocking) when fill rate exceeds 100%."""
        if self.capacity_boxes and self.total_boxes > self.capacity_boxes:
            return {
                'warning': {
                    'title': 'Over Capacity',
                    'message': (
                        'Total boxes (%d) exceed container capacity (%d). '
                        'Fill rate: %.1f%%. Please review before confirming.'
                        % (self.total_boxes, self.capacity_boxes, self.fill_rate_pct)
                    ),
                }
            }

    # ─────────────────────────────────────────────────────────────────────────
    # Actions
    # ─────────────────────────────────────────────────────────────────────────

    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})
