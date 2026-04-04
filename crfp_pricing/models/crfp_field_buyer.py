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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('token'):
                vals['token'] = uuid.uuid4().hex
        return super().create(vals_list)

    def action_regenerate_token(self):
        for rec in self:
            rec.token = uuid.uuid4().hex
