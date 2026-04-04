"""
CR Farm Website — main HTTP controller.

Routes
------
GET  /crfarm                       Home page
GET  /crfarm/about                 About Us
GET  /crfarm/history               Company History
GET  /crfarm/products              Product Catalog (pulls crfp.website.product)
GET  /crfarm/gallery               Photo Gallery
GET  /crfarm/certifications        Certifications page
GET  /crfarm/contact               B2B Contact form
POST /crfarm/contact               Submit B2B lead → CRM + AI classification
GET  /crfarm/contact/thanks        Thank-you confirmation page
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

    def _get_website_products(self):
        """Return all active crfp.website.product records ordered by sequence."""
        return request.env['crfp.website.product'].sudo().search(
            [('active', '=', True)],
            order='sequence, name',
        )

    # ─── Pages ──────────────────────────────────────────────────────────────

    @http.route('/crfarm', type='http', auth='public', website=True)
    def home(self, **kwargs):
        website_products = self._get_website_products()
        return request.render('crfp_website.page_home', {
            'website_products': website_products,
        })

    @http.route('/crfarm/about', type='http', auth='public', website=True)
    def about(self, **kwargs):
        return request.render('crfp_website.page_about')

    @http.route('/crfarm/history', type='http', auth='public', website=True)
    def history(self, **kwargs):
        return request.render('crfp_website.page_history')

    @http.route('/crfarm/products', type='http', auth='public', website=True)
    def catalog(self, **kwargs):
        website_products = self._get_website_products()
        return request.render('crfp_website.page_catalog', {
            'website_products': website_products,
        })

    @http.route('/crfarm/gallery', type='http', auth='public', website=True)
    def gallery(self, **kwargs):
        return request.render('crfp_website.page_gallery')

    @http.route('/crfarm/certifications', type='http', auth='public', website=True)
    def certifications(self, **kwargs):
        return request.render('crfp_website.page_certifications')

    @http.route('/crfarm/contact', type='http', auth='public', website=True,
                methods=['GET', 'POST'])
    def contact(self, **kw):
        if request.httprequest.method == 'POST':
            return self._handle_contact_form(kw)
        return request.render('crfp_website.page_contact', {'error': None, 'values': {}})

    @http.route('/crfarm/contact/thanks', type='http', auth='public', website=True)
    def contact_thanks(self, **kwargs):
        return request.render('crfp_website.page_contact_thanks')

    # ─── B2B Lead form handler ───────────────────────────────────────────────

    def _handle_contact_form(self, kw):
        """Validate B2B form data, create CRM lead, trigger AI classification."""
        name = (kw.get('contact_name') or '').strip()
        company = (kw.get('company_name') or '').strip()
        email = (kw.get('email') or '').strip()
        phone = (kw.get('phone') or '').strip()
        country = (kw.get('country') or '').strip()
        company_type = kw.get('company_type') or ''
        job_title = kw.get('job_title') or ''
        product_interest = kw.get('product_interest') or ''
        volume = kw.get('volume') or ''
        incoterm_pref = kw.get('incoterm_pref') or ''
        message = (kw.get('message') or '').strip()

        if not name or not email or not company:
            return request.render('crfp_website.page_contact', {
                'error': 'Please fill in your name, company, and email address.',
                'values': kw,
            })

        # Build descriptive lead title
        company_type_labels = {
            'importer': 'Importer/Wholesaler',
            'distributor': 'Distributor',
            'supermarket': 'Supermarket Chain',
            'foodservice': 'Food Service',
            'retailer': 'Ethnic Retailer',
            'other': 'Company',
        }
        interest_labels = {
            'tubers': 'Roots & Tubers',
            'coconut': 'Coconut',
            'sugar_cane': 'Sugar Cane',
            'vegetables': 'Vegetables',
            'mixed': 'Multiple Products',
            '': 'General Inquiry',
        }
        type_label = company_type_labels.get(company_type, 'Company')
        interest_label = interest_labels.get(product_interest, 'General Inquiry')
        lead_title = f'[Web] {type_label} — {interest_label} — {company}'

        # Build detailed description
        desc_parts = []
        if message:
            desc_parts.append(f'Message: {message}')
        if volume:
            desc_parts.append(f'Volume: {volume}')
        if incoterm_pref:
            desc_parts.append(f'Preferred Incoterm: {incoterm_pref}')
        if country:
            desc_parts.append(f'Country of Import: {country}')
        if job_title:
            desc_parts.append(f'Role: {job_title}')
        full_description = '\n'.join(desc_parts)

        source = self._get_or_create_source()

        vals = {
            'name': lead_title,
            'contact_name': name,
            'partner_name': company or name,
            'email_from': email,
            'phone': phone,
            'description': full_description,
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
                _logger.exception(
                    'crfp_website: immediate AI classification failed for lead %s', lead.id)
        except Exception:
            _logger.exception('crfp_website: failed to create CRM lead')
            return request.render('crfp_website.page_contact', {
                'error': 'An error occurred while sending your message. Please try again.',
                'values': kw,
            })

        return request.redirect('/crfarm/contact/thanks')
