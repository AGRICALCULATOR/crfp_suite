from odoo import models, fields


class CrfpTrackingEvent(models.Model):
    _name = 'crfp.tracking.event'
    _description = 'Tracking Event'
    _order = 'date_event desc'

    shipment_id = fields.Many2one('crfp.shipment', required=True, ondelete='cascade')
    container_id = fields.Many2one('crfp.shipment.container', string='Container',
                                    domain="[('shipment_id', '=', shipment_id)]")

    event_type = fields.Selection([
        ('gate_in', 'Gate In'),
        ('loaded', 'Loaded on Vessel'),
        ('departed', 'Departed'),
        ('transshipment_arrival', 'Transshipment Arrival'),
        ('transshipment_departure', 'Transshipment Departure'),
        ('arrived', 'Arrived at Destination'),
        ('customs_hold', 'Customs Hold'),
        ('customs_released', 'Customs Released'),
        ('gate_out', 'Gate Out'),
        ('delivered', 'Delivered to Client'),
        ('incident', 'Incident'),
        ('other', 'Other'),
    ], string='Event', required=True)

    date_event = fields.Datetime(string='Event Date', required=True)
    date_registered = fields.Datetime(string='Registered', default=fields.Datetime.now)
    location_text = fields.Char(string='Location',
                                 help='Free text: port name, terminal, at sea...')
    port_id = fields.Many2one('crfp.port', string='Port',
                               help='Select if event occurred at a known port')
    source = fields.Selection([
        ('manual', 'Manual Entry'),
        ('email', 'Email from Carrier'),
        ('carrier_update', 'Carrier Website/Update'),
        ('forwarder', 'Forwarder Update'),
        ('gps', 'GPS Device'),
        ('customer', 'Customer Report'),
        ('inspection', 'Inspection'),
    ], string='Source', required=True, default='manual')
    source_reference = fields.Char(string='Source Ref',
                                    help='Email ref, tracking ID, etc.')
    user_id = fields.Many2one('res.users', string='Registered By',
                               default=lambda self: self.env.user)
    notes = fields.Text(string='Notes')
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')
