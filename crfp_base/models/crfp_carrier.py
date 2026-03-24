from odoo import models, fields


class CrfpCarrier(models.Model):
    _name = 'crfp.carrier'
    _description = 'Shipping Carrier / Forwarder'
    _order = 'name'

    name = fields.Char(string='Name', required=True,
                       help='Commercial name: Maersk, MSC, CMA CGM...')
    carrier_type = fields.Selection([
        ('carrier', 'Carrier (Naviera)'),
        ('forwarder', 'Forwarder (Agente)'),
        ('both', 'Both'),
    ], string='Type', required=True, default='carrier')
    partner_id = fields.Many2one('res.partner', string='Contact in Odoo',
                                 help='Link to Odoo contact for this carrier')
    scac_code = fields.Char(string='SCAC Code',
                            help='Standard Carrier Alpha Code')
    contact_name = fields.Char(string='Operative Contact')
    contact_email = fields.Char(string='Operative Email')
    contact_phone = fields.Char(string='Operative Phone')
    tracking_url = fields.Char(string='Tracking URL',
                               help='Base URL for manual tracking reference')
    active = fields.Boolean(default=True)
    notes = fields.Text(string='Notes')
