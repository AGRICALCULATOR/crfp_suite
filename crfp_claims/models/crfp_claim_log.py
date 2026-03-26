from odoo import models, fields


class CrfpClaimLog(models.Model):
    _name = 'crfp.claim.log'
    _description = 'Claim Communication Log'
    _order = 'date desc, id desc'

    claim_id = fields.Many2one('crfp.claim', required=True, ondelete='cascade')
    date = fields.Datetime(string='Date', default=fields.Datetime.now)
    user_id = fields.Many2one('res.users', string='User',
                               default=lambda self: self.env.user)
    log_type = fields.Selection([
        ('note', 'Internal Note'),
        ('email', 'Email'),
        ('call', 'Phone Call'),
        ('decision', 'Decision'),
        ('status_change', 'Status Change'),
    ], string='Type', default='note')
    subject = fields.Char(string='Subject')
    body = fields.Html(string='Details')
    partner_id = fields.Many2one('res.partner', string='Contact')
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')
