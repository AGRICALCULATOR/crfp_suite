from odoo import models, fields, api


class CrfpShipmentContainer(models.Model):
    _name = 'crfp.shipment.container'
    _description = 'Shipment Container'
    _order = 'id'

    shipment_id = fields.Many2one('crfp.shipment', required=True, ondelete='cascade')
    container_type_id = fields.Many2one('crfp.container.type', string='Container Type')
    container_number = fields.Char(string='Container Number',
                                    help='e.g. MSKU1234567')
    seal_number = fields.Char(string='Seal Number')
    temperature_set = fields.Float(string='Temperature Set (°C)',
                                    help='Reefer temperature setting')
    gate_in_date = fields.Datetime(string='Gate-In Date')
    loading_date = fields.Datetime(string='Loading Date')
    vgm_weight = fields.Float(string='VGM Weight (kg)', digits=(12, 2),
                               help='Verified Gross Mass')
    notes = fields.Text(string='Notes')

    # Lines in this container
    line_ids = fields.One2many('crfp.shipment.line', 'container_id',
                                string='Lines in Container')

    # Computed totals
    total_boxes = fields.Integer(compute='_compute_totals', store=True)
    total_pallets = fields.Integer(compute='_compute_totals', store=True)
    total_net_weight = fields.Float(compute='_compute_totals', store=True, digits=(12, 2))
    total_gross_weight = fields.Float(compute='_compute_totals', store=True, digits=(12, 2))

    @api.depends('line_ids.boxes_actual', 'line_ids.pallets_actual',
                 'line_ids.net_weight_actual', 'line_ids.gross_weight_actual')
    def _compute_totals(self):
        for rec in self:
            rec.total_boxes = sum(l.boxes_actual for l in rec.line_ids)
            rec.total_pallets = sum(l.pallets_actual for l in rec.line_ids)
            rec.total_net_weight = sum(l.net_weight_actual for l in rec.line_ids)
            rec.total_gross_weight = sum(l.gross_weight_actual for l in rec.line_ids)
