from odoo import models, fields, api


class ContainerConfigWizard(models.TransientModel):
    _name = 'crfp.container.config.wizard'
    _description = 'Configure Container Wizard'

    # ── Context / link ──
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sales Order',
        help='Link the configuration to a specific sales order',
    )

    # ── Step 1: Container type ──
    container_type_id = fields.Many2one(
        'crfp.container.type',
        string='Container Type',
        required=True,
        help='Select the container type (e.g. 40ft HC Reefer)',
    )
    capacity_boxes = fields.Integer(
        string='Container Capacity (boxes)',
        compute='_compute_capacity',
        help='Standard capacity of the selected container type',
    )

    # ── Step 2: Pallet & box config ──
    pallet_config_id = fields.Many2one(
        'crfp.pallet.config',
        string='Pallet Configuration',
        help='Select a pallet config to auto-fill boxes/pallet and box weight',
    )
    box_type_id = fields.Many2one(
        'crfp.box.type',
        string='Box Type',
    )
    num_pallets = fields.Integer(
        string='Number of Pallets',
        default=20,
        required=True,
    )
    boxes_per_pallet = fields.Integer(
        string='Boxes per Pallet',
        default=66,
        required=True,
    )
    net_weight_per_box_kg = fields.Float(
        string='Net Weight / Box (kg)',
        digits=(12, 3),
    )

    # ── Step 3: Preview totals (computed, not stored) ──
    total_boxes = fields.Integer(
        string='Total Boxes',
        compute='_compute_totals',
    )
    total_weight_kg = fields.Float(
        string='Total Net Weight (kg)',
        compute='_compute_totals',
        digits=(12, 2),
    )
    total_volume_m3 = fields.Float(
        string='Est. Volume (m³)',
        compute='_compute_totals',
        digits=(12, 3),
    )
    fill_rate_pct = fields.Float(
        string='Fill Rate (%)',
        compute='_compute_totals',
        digits=(12, 1),
    )

    # ── Notes ──
    notes = fields.Text(string='Notes')

    # ─────────────────────────────────────────────────────────────────────────
    # Compute
    # ─────────────────────────────────────────────────────────────────────────

    @api.depends('container_type_id')
    def _compute_capacity(self):
        for rec in self:
            rec.capacity_boxes = rec.container_type_id.capacity_boxes if rec.container_type_id else 0

    @api.depends('num_pallets', 'boxes_per_pallet', 'net_weight_per_box_kg', 'capacity_boxes')
    def _compute_totals(self):
        BOX_VOLUME_M3 = 0.048
        for rec in self:
            total_boxes = (rec.num_pallets or 0) * (rec.boxes_per_pallet or 0)
            rec.total_boxes = total_boxes
            rec.total_weight_kg = total_boxes * (rec.net_weight_per_box_kg or 0.0)
            rec.total_volume_m3 = total_boxes * BOX_VOLUME_M3
            capacity = rec.capacity_boxes or 0
            rec.fill_rate_pct = (total_boxes / capacity * 100.0) if capacity else 0.0

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
    # Action
    # ─────────────────────────────────────────────────────────────────────────

    def action_save_config(self):
        """Create a crfp.container.config record from wizard data and open it."""
        self.ensure_one()
        config = self.env['crfp.container.config'].create({
            'sale_order_id': self.sale_order_id.id or False,
            'container_type_id': self.container_type_id.id,
            'pallet_config_id': self.pallet_config_id.id or False,
            'box_type_id': self.box_type_id.id or False,
            'num_pallets': self.num_pallets,
            'boxes_per_pallet': self.boxes_per_pallet,
            'net_weight_per_box_kg': self.net_weight_per_box_kg,
            'notes': self.notes or False,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'crfp.container.config',
            'res_id': config.id,
            'view_mode': 'form',
            'target': 'current',
        }
