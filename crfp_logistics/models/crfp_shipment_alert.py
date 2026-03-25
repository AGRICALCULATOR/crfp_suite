from odoo import models, fields


class CrfpShipmentAlert(models.Model):
    _name = 'crfp.shipment.alert'
    _description = 'Shipment Alert'
    _order = 'date_triggered desc'

    shipment_id = fields.Many2one('crfp.shipment', required=True, ondelete='cascade')
    alert_type = fields.Selection([
        ('deadline', 'Deadline'),
        ('document', 'Document'),
        ('temperature', 'Temperature'),
        ('delay', 'Delay'),
        ('shortage', 'Shortage'),
        ('custom', 'Custom'),
    ], string='Type', required=True, default='custom')
    severity = fields.Selection([
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
    ], string='Severity', default='warning')
    message = fields.Char(string='Message', required=True)
    date_triggered = fields.Datetime(string='Triggered', default=fields.Datetime.now)
    is_resolved = fields.Boolean(string='Resolved', default=False)
    resolved_by = fields.Many2one('res.users', string='Resolved By')
    resolved_date = fields.Datetime(string='Resolved Date')
    auto_generated = fields.Boolean(string='Auto-generated', default=False)

    def action_resolve(self):
        self.write({
            'is_resolved': True,
            'resolved_by': self.env.user.id,
            'resolved_date': fields.Datetime.now(),
        })
