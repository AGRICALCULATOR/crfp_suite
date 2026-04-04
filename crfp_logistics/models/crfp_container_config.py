from odoo import models, fields, api


class CrfpContainerConfig(models.Model):
    _name = 'crfp.container.config'
    _description = 'Container Configuration'
    _order = 'date desc, id desc'
    _rec_name = 'name'

    # ── Identity ──
    name = fields.Char(
        string='Reference',
        compute='_compute_name',
        store=True,
        help='Auto-generated reference for this container configuration',
    )
    date = fields.Date(string='Date', default=fields.Date.today, required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
    ], string='Status', default='draft', required=True)

    # ── Links ──
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sales Order',
        ondelete='set null',
        index=True,
    )

    # ── Container setup ──
    container_type_id = fields.Many2one(
        'crfp.container.type',
        string='Container Type',
        required=True,
        ondelete='restrict',
    )
    pallet_config_id = fields.Many2one(
        'crfp.pallet.config',
        string='Pallet Configuration',
        ondelete='set null',
        help='Select a pallet configuration to auto-fill boxes/pallet and weight',
    )
    box_type_id = fields.Many2one(
        'crfp.box.type',
        string='Box Type',
        ondelete='set null',
    )

    # ── Pallet & box inputs ──
    num_pallets = fields.Integer(
        string='Number of Pallets',
        default=20,
        help='Total pallets to load into the container',
    )
    boxes_per_pallet = fields.Integer(
        string='Boxes per Pallet',
        default=66,
        help='Number of boxes stacked on each pallet',
    )
    net_weight_per_box_kg = fields.Float(
        string='Net Weight / Box (kg)',
        digits=(12, 3),
        help='Net weight in kg of each box (auto-filled from Pallet Configuration)',
    )

    # ── Computed totals ──
    total_boxes = fields.Integer(
        string='Total Boxes',
        compute='_compute_totals',
        store=True,
    )
    total_weight_kg = fields.Float(
        string='Total Net Weight (kg)',
        compute='_compute_totals',
        store=True,
        digits=(12, 2),
    )
    total_volume_m3 = fields.Float(
        string='Est. Volume (m³)',
        compute='_compute_totals',
        store=True,
        digits=(12, 3),
        help='Estimated volume based on standard box dimensions (0.048 m³/box)',
    )
    capacity_boxes = fields.Integer(
        string='Container Capacity (boxes)',
        related='container_type_id.capacity_boxes',
        store=False,
        help='Standard box capacity of the selected container type',
    )
    fill_rate_pct = fields.Float(
        string='Fill Rate (%)',
        compute='_compute_totals',
        store=True,
        digits=(12, 1),
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

    @api.depends('num_pallets', 'boxes_per_pallet', 'net_weight_per_box_kg',
                 'container_type_id.capacity_boxes')
    def _compute_totals(self):
        # Standard export box: ~0.048 m³ (60×40×20 cm)
        BOX_VOLUME_M3 = 0.048
        for rec in self:
            total_boxes = (rec.num_pallets or 0) * (rec.boxes_per_pallet or 0)
            rec.total_boxes = total_boxes
            rec.total_weight_kg = total_boxes * (rec.net_weight_per_box_kg or 0.0)
            rec.total_volume_m3 = total_boxes * BOX_VOLUME_M3
            capacity = rec.container_type_id.capacity_boxes if rec.container_type_id else 0
            if capacity and total_boxes:
                rec.fill_rate_pct = (total_boxes / capacity) * 100.0
            else:
                rec.fill_rate_pct = 0.0

    # ─────────────────────────────────────────────────────────────────────────
    # Onchange
    # ─────────────────────────────────────────────────────────────────────────

    @api.onchange('pallet_config_id')
    def _onchange_pallet_config_id(self):
        """Auto-fill boxes_per_pallet and net_weight_per_box_kg from pallet config."""
        if self.pallet_config_id:
            self.boxes_per_pallet = self.pallet_config_id.boxes_per_pallet
            self.net_weight_per_box_kg = self.pallet_config_id.weight_kg

    # ─────────────────────────────────────────────────────────────────────────
    # Actions
    # ─────────────────────────────────────────────────────────────────────────

    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})
