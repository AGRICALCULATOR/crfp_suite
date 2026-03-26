from odoo import models, fields


class CrfpClaimEvidence(models.Model):
    _name = 'crfp.claim.evidence'
    _description = 'Claim Evidence'
    _order = 'date desc, id desc'

    claim_id = fields.Many2one('crfp.claim', required=True, ondelete='cascade')
    evidence_type = fields.Selection([
        ('photo', 'Photo'),
        ('video', 'Video'),
        ('quality_report', 'Quality Report'),
        ('inspection', 'Inspection Report'),
        ('temperature_log', 'Temperature Log'),
        ('document', 'Document'),
        ('email', 'Email'),
        ('other', 'Other'),
    ], string='Type', required=True)
    name = fields.Char(string='Description')
    date = fields.Datetime(string='Evidence Date', default=fields.Datetime.now)
    source = fields.Selection([
        ('customer', 'Customer'),
        ('internal', 'Internal'),
        ('carrier', 'Carrier'),
        ('inspector', 'Inspector'),
        ('forwarder', 'Forwarder'),
        ('insurance', 'Insurance'),
    ], string='Source')
    attachment_ids = fields.Many2many('ir.attachment', string='Files')
    notes = fields.Text(string='Notes')
