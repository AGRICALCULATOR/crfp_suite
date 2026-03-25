from odoo import models, fields


class CrfpTrackingPosition(models.Model):
    _name = 'crfp.tracking.position'
    _description = 'Tracking Position Report'
    _order = 'date desc'

    shipment_id = fields.Many2one('crfp.shipment', required=True, ondelete='cascade')
    container_id = fields.Many2one('crfp.shipment.container', string='Container')
    date = fields.Datetime(string='Date', required=True, default=fields.Datetime.now)
    latitude = fields.Float(string='Latitude', digits=(10, 6))
    longitude = fields.Float(string='Longitude', digits=(10, 6))
    location_text = fields.Char(string='Location', required=True,
                                 help='Always required: human-readable location')
    source = fields.Selection([
        ('manual', 'Manual Entry'),
        ('gps', 'GPS Device'),
        ('carrier_website', 'Carrier Website'),
        ('email', 'Email'),
        ('forwarder', 'Forwarder'),
    ], string='Source', default='manual', required=True)
    user_id = fields.Many2one('res.users', string='Registered By',
                               default=lambda self: self.env.user)
    notes = fields.Text(string='Notes')
