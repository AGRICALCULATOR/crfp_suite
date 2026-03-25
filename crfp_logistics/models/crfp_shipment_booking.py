from odoo import models, fields, api


class CrfpShipmentBooking(models.Model):
    _name = 'crfp.shipment.booking'
    _description = 'Shipment Booking'
    _order = 'create_date desc'
    _inherit = ['mail.thread']
    _rec_name = 'booking_reference'

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
    container_number = fields.Char(string='Container Number',
                                    help='Container number assigned by carrier on booking confirmation')
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

    def name_get(self):
        return [(r.id, r.booking_reference or ("Booking #%d" % r.id)) for r in self]

    @api.onchange('shipment_id')
    def _onchange_shipment_id(self):
        if not self.shipment_id:
            return
        ship = self.shipment_id
        self.carrier_partner_id = ship.carrier_partner_id
        self.vessel_name = ship.vessel_name
        self.voyage_number = ship.voyage_number
        self.container_type_id = ship.container_type_id
        self.etd = ship.etd
        self.eta = ship.eta
        self.cutoff_date = ship.cutoff_date
        # Try to get freight cost from quotation
        if ship.crfp_quotation_id and ship.crfp_quotation_id.freight_quote_id:
            self.freight_cost = ship.crfp_quotation_id.freight_quote_id.all_in_freight

    def action_confirm(self):
        self.write({'state': 'confirmed', 'confirmation_date': fields.Date.today()})
        # Sync container number and cutoff to shipment
        for rec in self:
            if rec.shipment_id:
                vals = {}
                if rec.cutoff_date:
                    vals['cutoff_date'] = rec.cutoff_date
                if rec.vessel_name:
                    vals['vessel_name'] = rec.vessel_name
                if rec.voyage_number:
                    vals['voyage_number'] = rec.voyage_number
                if rec.container_number and rec.shipment_id.container_ids:
                    # Update first container number
                    rec.shipment_id.container_ids[0].write({
                        'container_number': rec.container_number
                    })
                if vals:
                    rec.shipment_id.write(vals)

    def action_cancel(self):
        self.write({'state': 'cancelled'})
