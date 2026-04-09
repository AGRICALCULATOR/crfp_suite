from odoo import models, fields, api


class CrfpQuotationLine(models.Model):
    _name = 'crfp.quotation.line'
    _description = 'Export Quotation Product Line'
    _order = 'sequence, id'

    quotation_id = fields.Many2one('crfp.quotation', string='Quotation',
                                    required=True, ondelete='cascade')
    crfp_product_id = fields.Many2one('crfp.product', string='Product',
                                       required=True)
    sequence = fields.Integer(related='crfp_product_id.sequence', store=True)

    # ★ SKU link — per line, not per product (one base product has many SKUs)
    product_id = fields.Many2one(
        'product.product', string='Odoo SKU',
        help='Select the specific Odoo product/variant for this line. '
             'Required to create a Sale Order.')

    # Editable per-line parameters
    raw_price_crc = fields.Float(string='Raw Price (CRC)', digits=(12, 2))
    net_kg = fields.Float(string='Net Kg')
    box_cost = fields.Float(string='Box Cost (USD)', digits=(12, 2))
    labor_per_kg = fields.Float(digits=(12, 4))
    materials_per_kg = fields.Float(digits=(12, 4))
    indirect_per_kg = fields.Float(digits=(12, 4))
    profit = fields.Float(string='Profit (USD)', digits=(12, 2))

    # Calculated results
    purchase_cost = fields.Float(string='Purchase Cost (USD)', digits=(12, 4))
    packing_cost = fields.Float(string='Packing Cost (USD)', digits=(12, 4))
    exw_price = fields.Float(string='EXW Price (USD)', digits=(12, 2))
    logistics_per_box = fields.Float(string='Logistics/Box (USD)', digits=(12, 4))
    final_price = fields.Float(string='Final Price (USD)', digits=(12, 2))
    gross_lbs = fields.Float(string='Gross Lbs', digits=(12, 1))
    gross_kg = fields.Float(string='Gross Kg', compute='_compute_gross_kg', store=True, digits=(12, 1))

    # Order / pallet config
    pallets = fields.Integer(string='Pallets', default=0)
    boxes_per_pallet = fields.Integer(string='Boxes/Pallet', default=66)
    include_in_pdf = fields.Boolean(string='Include', default=True)

    # Computed fields for quotation form
    total_boxes = fields.Integer(string='Total Boxes', compute='_compute_totals', store=True)
    pallet_price = fields.Float(string='Price/Pallet', compute='_compute_totals', store=True, digits=(12, 2))
    line_total = fields.Float(string='Line Total', compute='_compute_totals', store=True, digits=(12, 2))

    @api.depends('gross_lbs')
    def _compute_gross_kg(self):
        for rec in self:
            rec.gross_kg = rec.gross_lbs / 2.20462 if rec.gross_lbs else 0.0

    @api.depends('pallets', 'boxes_per_pallet', 'final_price')
    def _compute_totals(self):
        for rec in self:
            rec.total_boxes = rec.pallets * rec.boxes_per_pallet
            rec.pallet_price = rec.final_price * rec.boxes_per_pallet
            rec.line_total = rec.final_price * rec.total_boxes

    @api.onchange('crfp_product_id')
    def _onchange_product(self):
        if self.crfp_product_id:
            p = self.crfp_product_id
            self.raw_price_crc = p.raw_price_crc
            self.net_kg = p.net_kg
            self.box_cost = p.default_box_cost
            self.labor_per_kg = p.labor_per_kg
            self.materials_per_kg = p.materials_per_kg
            self.indirect_per_kg = p.indirect_per_kg
            self.profit = p.default_profit
            # Pre-fill SKU from base product if set
            if p.product_id:
                self.product_id = p.product_id.id

    # ─────────────────────────────────────────────────────────────────────────
    # BP-01: Python calculation backup — mirrors calculator_service.js exactly
    # ─────────────────────────────────────────────────────────────────────────

    def _compute_all_prices(self):
        """
        Recalculate all price fields for these lines.
        Replicates calcSingleProduct() from calculator_service.js.
        Only recalculates lines in draft quotations.
        """
        for line in self:
            q = line.quotation_id
            if q.state != 'draft':
                continue

            exchange_rate = q.exchange_rate or 503
            product = line.crfp_product_id

            # ── 1. Purchase Cost (mirrors calcPurchaseCost) ──
            raw = line.raw_price_crc or 0
            kg = line.net_kg or 0
            if product.purchase_formula == 'quintal':
                purchase_cost = (1 * kg / 46) * (raw / exchange_rate)
            else:
                purchase_cost = (kg * raw) / exchange_rate

            # ── 2. Gross Weight (mirrors calcGrossLbs) ──
            if product.gross_weight_type == 'zero':
                gross_lbs = 0
            elif product.gross_weight_type == 'no_tare':
                gross_lbs = kg * 2.2
            else:
                gross_lbs = kg * 2.2 + 2

            # ── 3. Packing Cost (mirrors calcPackingCost) ──
            txk = (line.labor_per_kg or 0) + (line.materials_per_kg or 0) + (line.indirect_per_kg or 0)
            box_cost = line.box_cost or 0
            calc_type = product.calc_type or 'standard'
            if calc_type == 'flat_no_box':
                packing_cost = txk
            elif calc_type == 'flat_plus_box':
                packing_cost = txk + box_cost
            elif calc_type == 'kg_no_box':
                packing_cost = txk * kg
            else:  # standard
                packing_cost = (txk * kg) + box_cost

            # ── 4. EXW Price ──
            exw_price = purchase_cost + packing_cost + (line.profit or 0)

            # ── 5. Logistics per box (mirrors calcLogisticsPerBox) ──
            total_boxes = q.total_boxes or 1386
            fq = q.freight_quote_id

            # Fixed costs per box (zeroed if included in freight quote)
            fr_pb = (fq.all_in_freight / total_boxes) if fq else 0
            t_pb = 0 if (fq and fq.inc_transport) else (q.fc_transport or 0) / total_boxes
            fu_pb = (q.fc_fumigation or 0) / total_boxes  # never included in quote
            po_pb = 0 if (fq and fq.inc_thc_origin) else (q.fc_thc_origin or 0) / total_boxes
            ag_pb = 0 if (fq and fq.inc_broker) else (q.fc_broker or 0) / total_boxes
            td_pb = 0 if (fq and fq.inc_thc_dest) else (q.fc_thc_dest or 0) / total_boxes
            fd_pb = 0 if (fq and fq.inc_fumig_dest) else (q.fc_fumig_dest or 0) / total_boxes
            de_pb = 0 if (fq and fq.inc_inland_dest) else (q.fc_inland_dest or 0) / total_boxes

            # Incoterm matrix flags
            im = self.env['crfp.incoterm.matrix'].search(
                [('code', '=', q.incoterm)], limit=1)

            logistics = fr_pb + t_pb + fu_pb + po_pb + ag_pb

            # Destination costs (controlled by incoterm)
            ins_pct = q.fc_insurance_pct or 0
            ins_pb = (exw_price * ins_pct / 100) if (im and im.inc_insurance) else 0
            logistics += ins_pb

            if im and im.inc_thc_dest:
                logistics += td_pb
            if im and im.inc_fumig_dest:
                logistics += fd_pb
            if im and im.inc_inland_dest:
                logistics += de_pb

            # Duties (DDP only)
            duties_pct = q.fc_duties_pct or 0
            if im and im.inc_duties and duties_pct:
                cif_base = exw_price + fr_pb + ins_pb
                logistics += cif_base * (duties_pct / 100)

            # ── 6. Final Price ──
            final_price = exw_price + logistics

            # Write results (same rounding as JS)
            line.write({
                'purchase_cost': round(purchase_cost, 4),
                'packing_cost': round(packing_cost, 4),
                'exw_price': round(exw_price, 2),
                'logistics_per_box': round(logistics, 4),
                'final_price': round(final_price, 2),
                'gross_lbs': round(gross_lbs, 1),
            })
