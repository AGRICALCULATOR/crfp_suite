from odoo import models, fields, api


class ContainerConfigWizardLine(models.TransientModel):
    _name = 'crfp.container.config.wizard.line'
    _description = 'Container Config Wizard — Product Line'
    _order = 'sequence, id'

    wizard_id = fields.Many2one(
        'crfp.container.config.wizard',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(default=10)

    product_id = fields.Many2one('product.product', string='Product', ondelete='restrict')
    pallet_config_id = fields.Many2one(
        'crfp.pallet.config', string='Pallet Config', ondelete='set null',
    )
    num_pallets = fields.Integer(string='Pallets', default=1, required=True)
    boxes_per_pallet = fields.Integer(string='Boxes/Pallet', default=66, required=True)
    net_weight_per_box_kg = fields.Float(string='Net Weight/Box (kg)', digits=(12, 3))
    gross_weight_per_box_kg = fields.Float(string='Gross Weight/Box (kg)', digits=(12, 3))

    # Computed preview totals per line
    total_boxes = fields.Integer(string='Total Boxes', compute='_compute_totals')
    total_net_weight_kg = fields.Float(
        string='Total Net (kg)', compute='_compute_totals', digits=(12, 2),
    )
    total_gross_weight_kg = fields.Float(
        string='Total Gross (kg)', compute='_compute_totals', digits=(12, 2),
    )

    @api.depends('num_pallets', 'boxes_per_pallet',
                 'net_weight_per_box_kg', 'gross_weight_per_box_kg')
    def _compute_totals(self):
        for rec in self:
            boxes = (rec.num_pallets or 0) * (rec.boxes_per_pallet or 0)
            rec.total_boxes = boxes
            rec.total_net_weight_kg = boxes * (rec.net_weight_per_box_kg or 0.0)
            rec.total_gross_weight_kg = boxes * (rec.gross_weight_per_box_kg or 0.0)

    @api.onchange('pallet_config_id')
    def _onchange_pallet_config_id(self):
        if self.pallet_config_id:
            self.boxes_per_pallet = self.pallet_config_id.boxes_per_pallet
            self.net_weight_per_box_kg = self.pallet_config_id.weight_kg


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

    # ── Mode ──
    is_mixed = fields.Boolean(
        string='Mixed Products',
        default=False,
        help='Enable to configure multiple products with different packaging',
    )

    # ── Simple mode: single-product fields ──
    pallet_config_id = fields.Many2one(
        'crfp.pallet.config',
        string='Pallet Configuration',
        help='Select to auto-fill boxes/pallet and weight per box',
    )
    box_type_id = fields.Many2one('crfp.box.type', string='Box Type')
    num_pallets = fields.Integer(string='Number of Pallets', default=20, required=True)
    boxes_per_pallet = fields.Integer(string='Boxes per Pallet', default=66, required=True)
    net_weight_per_box_kg = fields.Float(string='Net Weight / Box (kg)', digits=(12, 3))
    gross_weight_per_box_kg = fields.Float(
        string='Gross Weight / Box (kg)', digits=(12, 3),
        help='Gross weight (net + box tare) per box. Required for logistics documents.',
    )

    # ── Mixed mode: per-product lines ──
    product_line_ids = fields.One2many(
        'crfp.container.config.wizard.line',
        'wizard_id',
        string='Product Lines',
    )

    # ── Preview totals ──
    total_boxes = fields.Integer(string='Total Boxes', compute='_compute_totals')
    total_weight_kg = fields.Float(
        string='Total Net Weight (kg)', compute='_compute_totals', digits=(12, 2),
    )
    total_gross_weight_kg = fields.Float(
        string='Total Gross Weight (kg)', compute='_compute_totals', digits=(12, 2),
    )
    total_volume_m3 = fields.Float(
        string='Est. Volume (m³)', compute='_compute_totals', digits=(12, 3),
    )
    fill_rate_pct = fields.Float(
        string='Fill Rate (%)', compute='_compute_totals', digits=(12, 1),
    )

    # ── Notes ──
    notes = fields.Text(string='Notes')

    # ─────────────────────────────────────────────────────────────────────────
    # Compute
    # ─────────────────────────────────────────────────────────────────────────

    @api.depends('container_type_id')
    def _compute_capacity(self):
        for rec in self:
            rec.capacity_boxes = (
                rec.container_type_id.capacity_boxes if rec.container_type_id else 0
            )

    @api.depends(
        'is_mixed',
        'num_pallets', 'boxes_per_pallet', 'net_weight_per_box_kg',
        'gross_weight_per_box_kg', 'capacity_boxes',
        'product_line_ids.total_boxes',
        'product_line_ids.total_net_weight_kg',
        'product_line_ids.total_gross_weight_kg',
    )
    def _compute_totals(self):
        BOX_VOLUME_M3 = 0.048
        for rec in self:
            if rec.is_mixed:
                total_boxes = sum(rec.product_line_ids.mapped('total_boxes'))
                total_net = sum(rec.product_line_ids.mapped('total_net_weight_kg'))
                total_gross = sum(rec.product_line_ids.mapped('total_gross_weight_kg'))
            else:
                total_boxes = (rec.num_pallets or 0) * (rec.boxes_per_pallet or 0)
                total_net = total_boxes * (rec.net_weight_per_box_kg or 0.0)
                total_gross = total_boxes * (rec.gross_weight_per_box_kg or 0.0)
            rec.total_boxes = total_boxes
            rec.total_weight_kg = total_net
            rec.total_gross_weight_kg = total_gross
            rec.total_volume_m3 = total_boxes * BOX_VOLUME_M3
            capacity = rec.capacity_boxes or 0
            rec.fill_rate_pct = (total_boxes / capacity * 100.0) if capacity and total_boxes else 0.0

    # ─────────────────────────────────────────────────────────────────────────
    # Onchange
    # ─────────────────────────────────────────────────────────────────────────

    @api.onchange('pallet_config_id')
    def _onchange_pallet_config_id(self):
        if self.pallet_config_id:
            self.boxes_per_pallet = self.pallet_config_id.boxes_per_pallet
            self.net_weight_per_box_kg = self.pallet_config_id.weight_kg

    # ─────────────────────────────────────────────────────────────────────────
    # Auto-fill from Sales Order
    # ─────────────────────────────────────────────────────────────────────────

    def action_autofill_from_so(self):
        """Populate product lines from the linked sale order's product lines."""
        self.ensure_one()
        if not self.sale_order_id:
            return
        PalletConfig = self.env['crfp.pallet.config']
        lines = []
        for so_line in self.sale_order_id.order_line.filtered(
            lambda l: l.product_id and l.product_type == 'product'
        ):
            product = so_line.product_id
            # Find matching pallet config by product keyword
            pallet_cfg = PalletConfig.search([
                ('product_keyword', '!=', False),
                ('active', '=', True),
            ], limit=0)
            matched_cfg = pallet_cfg.filtered(
                lambda p: p.product_keyword.upper() in (product.name or '').upper()
            )
            matched_cfg = matched_cfg[:1]  # take first match
            lines.append((0, 0, {
                'product_id': product.id,
                'pallet_config_id': matched_cfg.id if matched_cfg else False,
                'boxes_per_pallet': matched_cfg.boxes_per_pallet if matched_cfg else 66,
                'net_weight_per_box_kg': matched_cfg.weight_kg if matched_cfg else 0.0,
                'gross_weight_per_box_kg': 0.0,
                'num_pallets': 1,
            }))
        self.product_line_ids = [(5, 0, 0)] + lines
        self.is_mixed = True
        # Return the wizard action to stay open
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'crfp.container.config.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Save action
    # ─────────────────────────────────────────────────────────────────────────

    def action_save_config(self):
        """Create a crfp.container.config record (with lines if mixed) and open it."""
        self.ensure_one()
        config_vals = {
            'sale_order_id': self.sale_order_id.id or False,
            'container_type_id': self.container_type_id.id,
            'is_mixed': self.is_mixed,
            'pallet_config_id': self.pallet_config_id.id or False,
            'box_type_id': self.box_type_id.id or False,
            'num_pallets': self.num_pallets,
            'boxes_per_pallet': self.boxes_per_pallet,
            'net_weight_per_box_kg': self.net_weight_per_box_kg,
            'gross_weight_per_box_kg': self.gross_weight_per_box_kg,
            'notes': self.notes or False,
        }
        if self.is_mixed and self.product_line_ids:
            config_vals['product_line_ids'] = [
                (0, 0, {
                    'sequence': line.sequence,
                    'product_id': line.product_id.id or False,
                    'pallet_config_id': line.pallet_config_id.id or False,
                    'num_pallets': line.num_pallets,
                    'boxes_per_pallet': line.boxes_per_pallet,
                    'net_weight_per_box_kg': line.net_weight_per_box_kg,
                    'gross_weight_per_box_kg': line.gross_weight_per_box_kg,
                })
                for line in self.product_line_ids
            ]
        config = self.env['crfp.container.config'].create(config_vals)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'crfp.container.config',
            'res_id': config.id,
            'view_mode': 'form',
            'target': 'current',
        }
