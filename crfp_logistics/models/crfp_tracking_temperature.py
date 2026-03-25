from odoo import models, fields, api


class CrfpTrackingTemperature(models.Model):
    _name = 'crfp.tracking.temperature'
    _description = 'Temperature Log'
    _order = 'date desc'

    container_id = fields.Many2one('crfp.shipment.container', required=True,
                                    ondelete='cascade', string='Container')
    date = fields.Datetime(string='Date', required=True, default=fields.Datetime.now)
    temperature = fields.Float(string='Temperature (°C)', required=True)
    humidity = fields.Float(string='Humidity (%)')
    source = fields.Selection([
        ('manual', 'Manual Entry'),
        ('gps_device', 'GPS/Thermometer Device'),
        ('carrier_report', 'Carrier Report'),
        ('inspection', 'Inspection'),
    ], string='Source', default='manual', required=True)
    is_out_of_range = fields.Boolean(compute='_compute_out_of_range', store=True,
                                      string='Out of Range')
    user_id = fields.Many2one('res.users', string='Registered By',
                               default=lambda self: self.env.user)
    notes = fields.Text(string='Notes')

    @api.depends('temperature', 'container_id.temperature_set')
    def _compute_out_of_range(self):
        for rec in self:
            target = rec.container_id.temperature_set
            if target:
                rec.is_out_of_range = abs(rec.temperature - target) > 2.0
            else:
                rec.is_out_of_range = False
