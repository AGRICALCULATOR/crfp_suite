from odoo import models, fields, api


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    crfp_quotation_id = fields.Many2one('crfp.quotation', string='Export Quotation',
                                         help='Link to the CR Farm export quotation')
    crfp_shipment_id = fields.Many2one('crfp.shipment', string='Shipment',
                                        compute='_compute_crfp_shipment', store=False)

    def _compute_crfp_shipment(self):
        for rec in self:
            shipment = self.env['crfp.shipment'].search([
                ('sale_order_id', '=', rec.id)
            ], limit=1)
            rec.crfp_shipment_id = shipment.id if shipment else False

    def action_create_shipment(self):
        """Create a shipment from this SO with ALL data pre-filled."""
        self.ensure_one()

        # Find linked quotation
        quotation = self.env['crfp.quotation'].search([
            ('sale_order_id', '=', self.id)
        ], limit=1)
        if not quotation and hasattr(self, 'crfp_quotation_id') and self.crfp_quotation_id:
            quotation = self.crfp_quotation_id

        # Build shipment vals with all available data
        vals = {
            'sale_order_id': self.id,
            'partner_id': self.partner_id.id,
        }

        if quotation:
            vals['crfp_quotation_id'] = quotation.id
            vals['incoterm'] = quotation.incoterm
            if quotation.port_id:
                vals['port_destination_id'] = quotation.port_id.id
            if quotation.container_type_id:
                vals['container_type_id'] = quotation.container_type_id.id
            if quotation.etd:
                vals['etd'] = quotation.etd
            if quotation.eta:
                vals['eta'] = quotation.eta
            if quotation.vessel_name:
                vals['vessel_name'] = quotation.vessel_name
            if quotation.shipping_company:
                vals['shipping_company'] = quotation.shipping_company
            # Carrier from freight quote
            if quotation.freight_quote_id:
                fq = quotation.freight_quote_id
                if fq.carrier_partner_id:
                    vals['carrier_partner_id'] = fq.carrier_partner_id.id
                # Freight cost for reference
                if fq.all_in_freight:
                    vals['freight_cost'] = fq.all_in_freight
            # Default consignee = client
            vals['consignee_id'] = self.partner_id.id

        shipment = self.env['crfp.shipment'].create(vals)

        # Create shipment lines from SO + quotation data
        shipment._create_lines_from_so_and_quotation(quotation)

        # Auto-create one container if container type is set
        if shipment.container_type_id:
            self.env['crfp.shipment.container'].create({
                'shipment_id': shipment.id,
                'container_type_id': shipment.container_type_id.id,
            })

        # Auto-load documents and checklist
        shipment._auto_load_documents()
        shipment._auto_load_checklist()

        # Generate commodity description
        shipment._generate_commodity_description()

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'crfp.shipment',
            'res_id': shipment.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_shipment(self):
        """Open the linked Shipment."""
        self.ensure_one()
        if not self.crfp_shipment_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'crfp.shipment',
            'res_id': self.crfp_shipment_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
