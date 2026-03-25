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
        """Create a shipment from this SO."""
        self.ensure_one()
        shipment = self.env['crfp.shipment'].create({
            'sale_order_id': self.id,
        })
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
