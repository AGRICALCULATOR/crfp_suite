from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    crfp_shipment_id = fields.Many2one(
        'crfp.shipment', string='Shipment',
        compute='_compute_crfp_shipment_id', store=False,
        help='Linked shipment (commercial or proforma invoice)',
    )

    def _compute_crfp_shipment_id(self):
        """Find the shipment linked to this invoice via commercial_invoice_id or proforma_invoice_id."""
        Shipment = self.env['crfp.shipment']
        for move in self:
            ship = Shipment.search([
                '|',
                ('commercial_invoice_id', '=', move.id),
                ('proforma_invoice_id', '=', move.id),
            ], limit=1)
            move.crfp_shipment_id = ship
