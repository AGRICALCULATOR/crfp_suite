"""
CR Farm Website — main HTTP controller.

Routes
------
GET  /crfarm                  Home page
GET  /crfarm/about            About Us
GET  /crfarm/history          Company History
GET  /crfarm/products         Product Catalog (pulls crfp.product records)
GET  /crfarm/contact          Contact / Lead Capture form
POST /crfarm/contact          Submit lead → CRM + AI classification
GET  /crfarm/contact/thanks   Thank-you confirmation page
"""
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

_WEBSITE_SOURCE_NAME = 'CR Farm Website'


class CrfarmWebsite(http.Controller):

    # ─── Helpers ────────────────────────────────────────────────────────────

    def _get_or_create_source(self):
        """Return (or create) the UTM source record for the CR Farm website."""
        Source = request.env['utm.source'].sudo()
        source = Source.search([('name', '=', _WEBSITE_SOURCE_NAME)], limit=1)
        if not source:
            source = Source.create({'name': _WEBSITE_SOURCE_NAME})
        return source

    def _get_products_grouped(self):
        """Return crfp.product records grouped by category for templates."""
        products = request.env['crfp.product'].sudo().search(
            [('active', '=', True)],
            order='category, sequence, name',
        )
        category_labels = {
            'tubers': 'Roots & Tubers',
            'coconut': 'Coconut',
            'sugar_cane': 'Sugar Cane',
            'vegetables': 'Vegetables & Others',
        }
        groups = {}
        for p in products:
            cat = p.category
            if cat not in groups:
                groups[cat] = {'label': category_labels.get(cat, cat), 'products': []}
            groups[cat]['products'].append(p)
        return groups

    # ─── Pages ──────────────────────────────────────────────────────────────

    @http.route('/crfarm', type='http', auth='public', website=True)
    def home(self, **kwargs):
        product_groups = self._get_products_grouped()
        return request.render('crfp_website.page_home', {
            'product_groups': product_groups,
        })

    @http.route('/crfarm/about', type='http', auth='public', website=True)
    def about(self, **kwargs):
        return request.render('crfp_website.page_about')

    @http.route('/crfarm/history', type='http', auth='public', website=True)
    def history(self, **kwargs):
        return request.render('crfp_website.page_history')

    @http.route('/crfarm/products', type='http', auth='public', website=True)
    def catalog(self, **kwargs):
        product_groups = self._get_products_grouped()
        return request.render('crfp_website.page_catalog', {
            'product_groups': product_groups,
        })

    @http.route('/crfarm/contact', type='http', auth='public', website=True, methods=['GET', 'POST'])
    def contact(self, **kw):
        if request.httprequest.method == 'POST':
            return self._handle_contact_form(kw)
        return request.render('crfp_website.page_contact', {'error': None, 'values': {}})

    @http.route('/crfarm/contact/thanks', type='http', auth='public', website=True)
    def contact_thanks(self, **kwargs):
        return request.render('crfp_website.page_contact_thanks')

    # ─── Lead form handler ──────────────────────────────────────────────────

    def _handle_contact_form(self, kw):
        """Validate form data, create CRM lead, trigger AI classification."""
        name = (kw.get('contact_name') or '').strip()
        company = (kw.get('company_name') or '').strip()
        email = (kw.get('email') or '').strip()
        phone = (kw.get('phone') or '').strip()
        product_interest = kw.get('product_interest') or ''
        message = (kw.get('message') or '').strip()

        if not name or not email:
            return request.render('crfp_website.page_contact', {
                'error': 'Please fill in your name and email address.',
                'values': kw,
            })

        interest_labels = {
            'tubers': 'Roots & Tubers',
            'coconut': 'Coconut',
            'sugar_cane': 'Sugar Cane',
            'vegetables': 'Vegetables',
            'mixed': 'Multiple Products',
            '': 'General Inquiry',
        }
        interest_label = interest_labels.get(product_interest, 'General Inquiry')
        lead_title = f'[Web] {interest_label} — {company or name}'

        source = self._get_or_create_source()

        vals = {
            'name': lead_title,
            'contact_name': name,
            'partner_name': company or name,
            'email_from': email,
            'phone': phone,
            'description': message,
            'source_id': source.id,
            'crfp_from_website': True,
            'crfp_ai_classified': False,
        }

        try:
            lead = request.env['crm.lead'].sudo().create(vals)
            # Attempt immediate AI classification; cron handles failures
            try:
                lead._classify_with_ai()
            except Exception:
                _logger.exception('crfp_website: immediate AI classification failed for lead %s', lead.id)
        except Exception:
            _logger.exception('crfp_website: failed to create CRM lead')
            return request.render('crfp_website.page_contact', {
                'error': 'An error occurred while sending your message. Please try again.',
                'values': kw,
            })

        return request.redirect('/crfarm/contact/thanks')
