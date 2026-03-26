from odoo import models, fields, api


class CrfpShipmentClaims(models.Model):
    _inherit = 'crfp.shipment'

    claim_ids = fields.One2many('crfp.claim', 'shipment_id', string='Claims')
    claim_count = fields.Integer(compute='_compute_claim_count')

    @api.depends('claim_ids')
    def _compute_claim_count(self):
        for rec in self:
            rec.claim_count = len(rec.claim_ids)

    def action_report_claim(self):
        """Create a new claim pre-filled from this shipment."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'crfp.claim',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_shipment_id': self.id,
                'default_partner_id': self.partner_id.id if self.partner_id else False,
                'default_sale_order_id': self.sale_order_id.id if self.sale_order_id else False,
                'default_container_id': self.container_ids[0].id if self.container_ids else False,
            },
        }

    def action_view_claims(self):
        """Open claims for this shipment."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'crfp.claim',
            'view_mode': 'list,form',
            'domain': [('shipment_id', '=', self.id)],
            'context': {'default_shipment_id': self.id},
            'target': 'current',
        }
