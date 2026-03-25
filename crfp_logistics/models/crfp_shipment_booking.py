from odoo import models, fields


class CrfpShipmentBooking(models.Model):
    _name = 'crfp.shipment.booking'
    _description = 'Shipment Booking'
    _order = 'create_date desc'
    _inherit = ['mail.thread']

    shipment_id = fields.Many2one('crfp.shipment', string='Shipment', ondelete='cascade')
    state = fields.Selection([
        ('requested', 'Requested'),
        ('confirmed', 'Confirmed'),
        ('amended', 'Amended'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='requested', tracking=True)

    booking_reference = fields.Char(string='Booking Reference', tracking=True)
    carrier_partner_id = fields.Many2one('res.partner', string='Carrier')
    vessel_name = fields.Char(string='Vessel')
    voyage_number = fields.Char(string='Voyage')
    container_type_id = fields.Many2one('crfp.container.type', string='Container Type')
    containers_qty = fields.Integer(string='Containers Qty', default=1)
    cutoff_date = fields.Datetime(string='Cutoff Date')
    etd = fields.Date(string='ETD')
    eta = fields.Date(string='ETA')
    request_date = fields.Date(string='Request Date', default=fields.Date.today)
    confirmation_date = fields.Date(string='Confirmation Date')
    freight_cost = fields.Float(string='Freight Cost (USD)', digits=(12, 2))
    currency_id = fields.Many2one('res.currency', string='Currency',
                                   default=lambda self: self.env.ref('base.USD', raise_if_not_found=False))
    contact_person = fields.Char(string='Contact Person')
    notes = fields.Text(string='Notes')

    def action_confirm(self):
        self.write({'state': 'confirmed', 'confirmation_date': fields.Date.today()})

    def action_cancel(self):
        self.write({'state': 'cancelled'})
