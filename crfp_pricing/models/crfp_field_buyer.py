import uuid
from odoo import models, fields, api


class CrfpFieldBuyer(models.Model):
    _name = 'crfp.field.buyer'
    _description = 'Field Buyer'
    _rec_name = 'name'

    name = fields.Char(string='Name', required=True)
    phone = fields.Char(string='Phone')
    token = fields.Char(string='Access Token', readonly=True, copy=False, index=True)
    active = fields.Boolean(default=True)
    partner_id = fields.Many2one('res.partner', string='Contact')
    allowed_product_ids = fields.Many2many('crfp.product', string='Allowed Products')

    public_url = fields.Char(string='Price List Link', compute='_compute_public_url')

    @api.depends('token')
    def _compute_public_url(self):
        base = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
        for rec in self:
            if rec.token:
                rec.public_url = '%s/crfp/prices/%s' % (base, rec.token)
            else:
                rec.public_url = ''

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('token'):
                vals['token'] = uuid.uuid4().hex
        return super().create(vals_list)

    def action_regenerate_token(self):
        for rec in self:
            rec.token = uuid.uuid4().hex

    def action_copy_link(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Link copiado',
                'message': self.public_url,
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.client',
                    'tag': 'crfp_pricing.copy_to_clipboard',
                    'params': {'text': self.public_url},
                },
            },
        }
