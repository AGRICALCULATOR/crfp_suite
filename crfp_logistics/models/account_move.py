from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    crfp_shipment_id = fields.Many2one(
        'crfp.shipment', string='Shipment',
        compute='_compute_crfp_shipment_id', store=False,
        help='Linked shipment found via direct link or sale order',
    )

    def _compute_crfp_shipment_id(self):
        """Find the shipment linked to this invoice.

        Search order:
        1. Direct link: commercial_invoice_id or proforma_invoice_id
        2. Via Sale Order: invoice → sale order → shipment.sale_order_id
        """
        Shipment = self.env['crfp.shipment']
        for move in self:
            # 1. Direct link
            ship = Shipment.search([
                '|',
                ('commercial_invoice_id', '=', move.id),
                ('proforma_invoice_id', '=', move.id),
            ], limit=1)
            if not ship:
                # 2. Via Sale Order (invoice_line → sale_line → sale_order → shipment)
                sale_orders = move.invoice_line_ids.sale_line_ids.order_id
                if sale_orders:
                    ship = Shipment.search([
                        ('sale_order_id', 'in', sale_orders.ids),
                    ], limit=1, order='create_date desc')
            move.crfp_shipment_id = ship
