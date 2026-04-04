from odoo import http
from odoo.http import request


class FieldBuyerPortal(http.Controller):

    @http.route('/crfp/prices/<string:token>', type='http', auth='public')
    def field_buyer_prices(self, token, **kwargs):
        buyer = request.env['crfp.field.buyer'].sudo().search([
            ('token', '=', token),
            ('active', '=', True),
        ], limit=1)
        if not buyer:
            return request.not_found()
        price_list = request.env['crfp.price.list'].sudo().search(
            [('status', '=', 'active')],
            order='year desc, week_number desc',
            limit=1,
        )
        return request.render('crfp_pricing.field_buyer_portal_template', {
            'buyer': buyer,
            'price_list': price_list,
        })
