from odoo import models, fields


class CrfpShipmentLog(models.Model):
    _name = 'crfp.shipment.log'
    _description = 'Shipment Communication Log'
    _order = 'date desc'

    shipment_id = fields.Many2one('crfp.shipment', required=True, ondelete='cascade')
    date = fields.Datetime(string='Date', default=fields.Datetime.now, required=True)
    user_id = fields.Many2one('res.users', string='Logged By',
                               default=lambda self: self.env.user)
    log_type = fields.Selection([
        ('note', 'Note'),
        ('email_sent', 'Email Sent'),
        ('email_received', 'Email Received'),
        ('call', 'Phone Call'),
        ('meeting', 'Meeting'),
        ('status_change', 'Status Change'),
    ], string='Type', default='note', required=True)
    subject = fields.Char(string='Subject')
    body = fields.Html(string='Details')
    partner_id = fields.Many2one('res.partner', string='Contact')
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')
