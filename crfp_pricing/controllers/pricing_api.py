import json
import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class CrfpPricingAPI(http.Controller):
    """JSON API endpoints for the Owl calculator frontend."""

    # ─── MASTER DATA ────────────────────────────────────────────

    @http.route('/crfp/api/master-data', type='json', auth='user')
    def get_master_data(self):
        """Return all master data needed by the calculator in one call."""
        env = request.env

        products = env['crfp.product'].search_read(
            [('active', '=', True)],
            ['id', 'name', 'category', 'sequence', 'raw_price_crc', 'net_kg',
             'default_box_cost', 'labor_per_kg', 'materials_per_kg',
             'indirect_per_kg', 'default_profit', 'calc_type',
             'purchase_formula', 'gross_weight_type', 'product_id'],
            order='category, sequence',
        )

        ports = env['crfp.port'].search_read(
            [('active', '=', True)],
            ['id', 'code', 'name', 'country', 'region'],
            order='region, name',
        )

        carriers = env['crfp.carrier'].search_read(
            [('active', '=', True)],
            ['id', 'name', 'carrier_type', 'scac_code'],
            order='name',
        )

        container_types = env['crfp.container.type'].search_read(
            [('active', '=', True)],
            ['id', 'code', 'name', 'capacity_boxes', 'is_reefer'],
            order='sequence',
        )

        box_types = env['crfp.box.type'].search_read(
            [('active', '=', True)],
            ['id', 'name', 'brand', 'cost', 'notes'],
            order='sequence',
        )

        pallet_configs = env['crfp.pallet.config'].search_read(
            [('active', '=', True)],
            ['id', 'product_keyword', 'weight_kg', 'boxes_per_pallet'],
        )

        incoterm_matrix = env['crfp.incoterm.matrix'].search_read(
            [],
            ['code', 'inc_transport', 'inc_fumigation', 'inc_thc_origin',
             'inc_broker', 'inc_freight', 'inc_insurance', 'inc_thc_dest',
             'inc_fumig_dest', 'inc_broker_dest', 'inc_inland_dest',
             'inc_duties'],
            order='sequence',
        )

        fixed_cost = env['crfp.fixed.cost'].get_fixed_costs()
        fc_data = {
            'transport': fixed_cost.transport,
            'thc_origin': fixed_cost.thc_origin,
            'fumigation': fixed_cost.fumigation,
            'broker': fixed_cost.broker,
            'thc_dest': fixed_cost.thc_dest,
            'fumig_dest': fixed_cost.fumig_dest,
            'inland_dest': fixed_cost.inland_dest,
            'insurance_pct': fixed_cost.insurance_pct,
            'duties_pct': fixed_cost.duties_pct,
            'default_total_boxes': fixed_cost.default_total_boxes,
            'default_exchange_rate': fixed_cost.default_exchange_rate,
        }

        return {
            'products': products,
            'ports': ports,
            'carriers': carriers,
            'container_types': container_types,
            'box_types': box_types,
            'pallet_configs': pallet_configs,
            'incoterm_matrix': {r['code']: r for r in incoterm_matrix},
            'fixed_costs': fc_data,
        }

    # ─── FREIGHT QUOTES ─────────────────────────────────────────

    @http.route('/crfp/api/freight-quotes', type='json', auth='user')
    def get_freight_quotes(self, port_id=None):
        """Get freight quotes, optionally filtered by port."""
        domain = [('active', '=', True)]
        if port_id:
            domain.append(('port_id', '=', port_id))
        quotes = request.env['crfp.freight.quote'].search_read(
            domain,
            ['id', 'name', 'carrier_partner_id', 'carrier_name', 'port_id',
             'container_type_id', 'delivery_type', 'all_in_freight',
             'transit_days', 'routing', 'transship_port',
             'valid_from', 'valid_until', 'source', 'state',
             'inc_transport', 'inc_thc_origin', 'inc_broker',
             'inc_thc_dest', 'inc_inland_dest', 'inc_fumig_dest',
             'is_expired', 'notes'],
            order='all_in_freight asc',
        )
        return quotes

    @http.route('/crfp/api/freight-quote/save', type='json', auth='user')
    def save_freight_quote(self, vals):
        """Create or update a freight quote."""
        env = request.env['crfp.freight.quote']
        quote_id = vals.pop('id', None)
        if quote_id:
            record = env.browse(quote_id)
            record.write(vals)
            return record.id
        else:
            record = env.create(vals)
            return record.id

    @http.route('/crfp/api/freight-quote/delete', type='json', auth='user')
    def delete_freight_quote(self, quote_id):
        """Delete a freight quote."""
        request.env['crfp.freight.quote'].browse(quote_id).unlink()
        return True

    # ─── QUOTATIONS (SAVE / LOAD) ───────────────────────────────

    @http.route('/crfp/api/quotations', type='json', auth='user')
    def get_quotations(self):
        """List all saved quotations."""
        return request.env['crfp.quotation'].search_read(
            [],
            ['id', 'name', 'state', 'partner_id', 'incoterm',
             'port_id', 'exchange_rate', 'create_date',
             'sale_order_id', 'line_count', 'total_amount'],
            order='create_date desc',
            limit=100,
        )

    @http.route('/crfp/api/quotation/load', type='json', auth='user')
    def load_quotation(self, quotation_id):
        """Load full quotation with lines."""
        q = request.env['crfp.quotation'].browse(quotation_id)
        if not q.exists():
            return {'error': 'Quotation not found'}

        lines = []
        for l in q.line_ids:
            lines.append({
                'id': l.id,
                'crfp_product_id': l.crfp_product_id.id,
                'product_name': l.crfp_product_id.name,
                'raw_price_crc': l.raw_price_crc,
                'net_kg': l.net_kg,
                'box_cost': l.box_cost,
                'labor_per_kg': l.labor_per_kg,
                'materials_per_kg': l.materials_per_kg,
                'indirect_per_kg': l.indirect_per_kg,
                'profit': l.profit,
                'purchase_cost': l.purchase_cost,
                'packing_cost': l.packing_cost,
                'exw_price': l.exw_price,
                'logistics_per_box': l.logistics_per_box,
                'final_price': l.final_price,
                'gross_lbs': l.gross_lbs,
                'pallets': l.pallets,
                'boxes_per_pallet': l.boxes_per_pallet,
                'include_in_pdf': l.include_in_pdf,
            })

        return {
            'id': q.id,
            'name': q.name,
            'state': q.state,
            'partner_id': q.partner_id.id if q.partner_id else False,
            'partner_name': q.partner_id.name if q.partner_id else '',
            'client_type': q.client_type,
            'exchange_rate': q.exchange_rate,
            'incoterm': q.incoterm,
            'freight_quote_id': q.freight_quote_id.id if q.freight_quote_id else False,
            'port_id': q.port_id.id if q.port_id else False,
            'container_type_id': q.container_type_id.id if q.container_type_id else False,
            'total_boxes': q.total_boxes,
            'etd': str(q.etd) if q.etd else '',
            'eta': str(q.eta) if q.eta else '',
            'vessel_name': q.vessel_name or '',
            'shipping_company': q.shipping_company or '',
            'fc_transport': q.fc_transport,
            'fc_thc_origin': q.fc_thc_origin,
            'fc_fumigation': q.fc_fumigation,
            'fc_broker': q.fc_broker,
            'fc_thc_dest': q.fc_thc_dest,
            'fc_fumig_dest': q.fc_fumig_dest,
            'fc_inland_dest': q.fc_inland_dest,
            'fc_insurance_pct': q.fc_insurance_pct,
            'fc_duties_pct': q.fc_duties_pct,
            'sale_order_id': q.sale_order_id.id if q.sale_order_id else False,
            'lines': lines,
        }

    @http.route('/crfp/api/quotation/save', type='json', auth='user')
    def save_quotation(self, data):
        """Save (create or update) a full quotation with lines."""
        env = request.env
        quotation_id = data.get('id')
        lines_data = data.pop('lines', [])

        # Separate quotation header vals
        header_fields = [
            'name', 'partner_id', 'client_type', 'exchange_rate', 'incoterm',
            'freight_quote_id', 'port_id', 'container_type_id', 'total_boxes',
            'etd', 'eta', 'vessel_name', 'shipping_company',
            'fc_transport', 'fc_thc_origin', 'fc_fumigation', 'fc_broker',
            'fc_thc_dest', 'fc_fumig_dest', 'fc_inland_dest',
            'fc_insurance_pct', 'fc_duties_pct',
        ]
        vals = {k: data[k] for k in header_fields if k in data}

        # Clean empty dates
        for date_field in ('etd', 'eta'):
            if date_field in vals and not vals[date_field]:
                vals[date_field] = False

        # Clean empty M2O
        for m2o in ('partner_id', 'freight_quote_id', 'port_id', 'container_type_id'):
            if m2o in vals and not vals[m2o]:
                vals[m2o] = False

        if quotation_id:
            quotation = env['crfp.quotation'].browse(quotation_id)
            quotation.write(vals)
            # Delete existing lines and recreate
            quotation.line_ids.unlink()
        else:
            quotation = env['crfp.quotation'].create(vals)

        # Create lines
        for l in lines_data:
            line_vals = {
                'quotation_id': quotation.id,
                'crfp_product_id': l['crfp_product_id'],
                'raw_price_crc': l.get('raw_price_crc', 0),
                'net_kg': l.get('net_kg', 0),
                'box_cost': l.get('box_cost', 0),
                'labor_per_kg': l.get('labor_per_kg', 0),
                'materials_per_kg': l.get('materials_per_kg', 0),
                'indirect_per_kg': l.get('indirect_per_kg', 0),
                'profit': l.get('profit', 0),
                'purchase_cost': l.get('purchase_cost', 0),
                'packing_cost': l.get('packing_cost', 0),
                'exw_price': l.get('exw_price', 0),
                'logistics_per_box': l.get('logistics_per_box', 0),
                'final_price': l.get('final_price', 0),
                'gross_lbs': l.get('gross_lbs', 0),
                'pallets': l.get('pallets', 0),
                'boxes_per_pallet': l.get('boxes_per_pallet', 66),
                'include_in_pdf': l.get('include_in_pdf', True),
            }
            env['crfp.quotation.line'].create(line_vals)

        # Record price history
        env['crfp.price.history'].record_prices(quotation)

        return {'id': quotation.id, 'name': quotation.name}

    # ─── SALE ORDER CREATION ─────────────────────────────────────

    @http.route('/crfp/api/quotation/create-so', type='json', auth='user')
    def create_sale_order(self, quotation_id):
        """Create sale.order from a quotation."""
        quotation = request.env['crfp.quotation'].browse(quotation_id)
        if not quotation.exists():
            return {'error': 'Quotation not found'}
        result = quotation.action_create_sale_order()
        return {
            'sale_order_id': quotation.sale_order_id.id,
            'sale_order_name': quotation.sale_order_id.name,
        }

    # ─── PARTNERS ────────────────────────────────────────────────

    @http.route('/crfp/api/partners', type='json', auth='user')
    def get_partners(self):
        """Get customers for the client selector."""
        return request.env['res.partner'].search_read(
            [('customer_rank', '>', 0), ('active', '=', True)],
            ['id', 'name', 'email', 'country_id'],
            order='name',
            limit=200,
        )

    # ─── PRICE HISTORY ───────────────────────────────────────────

    @http.route('/crfp/api/price-history', type='json', auth='user')
    def get_price_history(self, product_id=None):
        """Get price history, optionally for a specific product."""
        domain = []
        if product_id:
            domain.append(('crfp_product_id', '=', product_id))
        return request.env['crfp.price.history'].search_read(
            domain,
            ['crfp_product_id', 'date', 'price_crc', 'exchange_rate', 'price_usd'],
            order='date desc',
            limit=520,  # ~52 weeks * 10 products
        )

    # ─── FIXED COSTS (save from calculator) ──────────────────────

    @http.route('/crfp/api/fixed-costs/save', type='json', auth='user')
    def save_fixed_costs(self, vals):
        """Update fixed costs from the calculator UI."""
        fc = request.env['crfp.fixed.cost'].get_fixed_costs()
        fc.write(vals)
        return True
