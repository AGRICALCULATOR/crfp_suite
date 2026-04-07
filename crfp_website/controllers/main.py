"""
CR Farm Website — main HTTP controller.

Routes for: Home, About, Products, Product Detail,
Certifications, Gallery, Contact, B2B Lead form submission.
"""
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

_WEBSITE_SOURCE_NAME = 'CR Farm Website'


class CrfarmWebsite(http.Controller):

    def _get_or_create_source(self):
        """Return (or create) the UTM source record for the CR Farm website."""
        Source = request.env['utm.source'].sudo()
        source = Source.search([('name', '=', _WEBSITE_SOURCE_NAME)], limit=1)
        if not source:
            source = Source.create({'name': _WEBSITE_SOURCE_NAME})
        return source

    # ── Page Routes ──────────────────────────────────────────────────────────

    @http.route(['/'], type='http', auth='public', website=True)
    def home(self, **kw):
        products = request.env['crfp.website.product'].sudo().search(
            [('active', '=', True)], order='sequence asc', limit=8)
        return request.render('crfp_website.crfarm_home', {'products': products})

    @http.route(['/about'], type='http', auth='public', website=True)
    def about(self, **kw):
        return request.render('crfp_website.crfarm_about', {})

    @http.route(['/products'], type='http', auth='public', website=True)
    def products(self, category='all', **kw):
        domain = [('active', '=', True)]
        if category and category != 'all':
            domain.append(('category', '=', category))
        products = request.env['crfp.website.product'].sudo().search(
            domain, order='sequence asc')
        return request.render('crfp_website.crfarm_products', {
            'products': products,
            'current_category': category,
        })

    @http.route(['/products/<int:product_id>'], type='http', auth='public', website=True)
    def product_detail(self, product_id, **kw):
        product = request.env['crfp.website.product'].sudo().browse(product_id)
        if not product.exists() or not product.active:
            return request.not_found()
        return request.render('crfp_website.crfarm_product_detail', {'product': product})

    @http.route(['/certifications'], type='http', auth='public', website=True)
    def certifications(self, **kw):
        return request.render('crfp_website.crfarm_certifications', {})

    @http.route(['/gallery'], type='http', auth='public', website=True)
    def gallery(self, **kw):
        return request.render('crfp_website.crfarm_gallery', {})

    @http.route(['/contact'], type='http', auth='public', website=True)
    def contact(self, **kw):
        countries = request.env['res.country'].sudo().search([], order='name asc')
        return request.render('crfp_website.crfarm_contact', {'countries': countries})

    # ── API / Form Submission ─────────────────────────────────────────────────

    @http.route('/contact/submit', type='jsonrpc', auth='public', website=True)
    def contact_submit(self, name, company, email, phone=None, country=None,
                       message=None, company_type=None, import_volume=None,
                       incoterm=None, **kw):
        """Create a CRM lead from the B2B contact form and trigger AI classification."""
        source = self._get_or_create_source()

        description_lines = []
        if company_type:
            description_lines.append(f'Tipo de empresa / Company type: {company_type}')
        if import_volume:
            description_lines.append(f'Volumen estimado / Import volume: {import_volume}')
        if incoterm:
            description_lines.append(f'Incoterm preferido / Preferred incoterm: {incoterm}')
        if message:
            description_lines.append(f'\nMensaje / Message:\n{message}')

        vals = {
            'name': f'[Website] {company or name}',
            'contact_name': name,
            'partner_name': company or name,
            'email_from': email,
            'phone': phone or '',
            'description': '\n'.join(description_lines),
            'crfp_from_website': True,
            'source_id': source.id,
            'type': 'lead',
        }

        if country:
            country_rec = request.env['res.country'].sudo().search(
                [('name', 'ilike', country)], limit=1)
            if country_rec:
                vals['country_id'] = country_rec.id

        lead = request.env['crm.lead'].sudo().create(vals)

        # Fire-and-forget AI classification
        try:
            lead._classify_with_ai()
        except Exception:
            _logger.exception('crfp_website: AI classification failed for lead %s', lead.id)

        return {'success': True, 'lead_id': lead.id}
