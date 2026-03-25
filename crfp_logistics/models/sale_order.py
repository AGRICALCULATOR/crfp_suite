from odoo import models, fields


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    crfp_quotation_id = fields.Many2one('crfp.quotation', string='Export Quotation',
                                         help='Link to the CR Farm export quotation')

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
