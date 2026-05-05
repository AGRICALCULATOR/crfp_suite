"""
Portal controller for field buyers to enter raw material prices (CRC).

Routes
------
GET  /crfp/prices/<token>       — Mobile-first form showing all active products
                                   with editable raw_price_crc inputs.
POST /crfp/prices/<token>/save  — Saves raw_price_crc to crfp.product records
                                   and logs to crfp.price.history.
"""
import datetime
import logging
from odoo import fields as odoo_fields
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class PricePortal(http.Controller):
    """Public portal for field buyers to enter raw material prices."""

    # ─── Helpers ────────────────────────────────────────────────────────────

    def _get_buyer(self, token):
        """Return the active field buyer for the given token, or None."""
        return request.env['crfp.field.buyer'].sudo().search(
            [('token', '=', token), ('active', '=', True)],
            limit=1,
        )

    def _get_active_products(self):
        """Return all active crfp.product records ordered by category/sequence."""
        return request.env['crfp.product'].sudo().search(
            [('active', '=', True)],
            order='category, sequence, name',
        )

    def _group_by_category(self, products):
        """Group a recordset of crfp.product by category selection value."""
        category_labels = dict(
            request.env['crfp.product'].sudo().fields_get(
                ['category'], attributes=['selection']
            )['category']['selection']
        )
        groups = {}
        for product in products:
            cat = product.category
            label = category_labels.get(cat, cat)
            if cat not in groups:
                groups[cat] = {'label': label, 'products': []}
            groups[cat]['products'].append(product)
        return groups

    def _current_week_year(self):
        """Return (week, year) for today's ISO week."""
        today = datetime.date.today()
        iso = today.isocalendar()
        return iso[1], iso[0]  # (week, year)

    # ─── GET: show form ─────────────────────────────────────────────────────

    @http.route('/crfp/prices/<string:token>', type='http', auth='public', website=False)
    def field_buyer_price_form(self, token, **kwargs):
        """Render the mobile-first price input form for the field buyer."""
        buyer = self._get_buyer(token)
        if not buyer:
            return request.not_found()

        # Log access stats
        buyer._register_access()

        products = self._get_active_products()
        product_groups = self._group_by_category(products)
        week, year = self._current_week_year()

        values = {
            'buyer': buyer,
            'product_groups': product_groups,
            'week': week,
            'year': year,
            'success': kwargs.get('success'),
            'error': kwargs.get('error'),
        }
        return request.render('crfp_pricing.field_buyer_price_form_template', values)

    # ─── POST: save prices ──────────────────────────────────────────────────

    @http.route('/crfp/prices/<string:token>/save', type='http', auth='public',
                methods=['POST'], csrf=True, website=False)
    def field_buyer_save_prices(self, token, **post):
        """Save submitted raw material prices and redirect with confirmation."""
        buyer = self._get_buyer(token)
        if not buyer:
            return request.not_found()

        week, year = self._current_week_year()
        Product = request.env['crfp.product'].sudo()
        History = request.env['crfp.price.history'].sudo()

        saved_count = 0
        errors = []

        for key, value in post.items():
            # Form fields named: price_<product_id>
            if not key.startswith('price_'):
                continue
            try:
                product_id = int(key[len('price_'):])
            except (ValueError, TypeError):
                continue

            raw_str = (value or '').strip().replace(',', '.')
            if not raw_str:
                continue

            try:
                raw_price = float(raw_str)
            except ValueError:
                errors.append('Precio inválido para producto %d: "%s"' % (product_id, raw_str))
                continue

            if raw_price < 0:
                errors.append('El precio no puede ser negativo (producto %d).' % product_id)
                continue

            product = Product.browse(product_id)
            if not product.exists() or not product.active:
                continue

            # Update raw price on the product
            product.write({'raw_price_crc': raw_price})

            # Record in price history
            # Search for existing record this week to update, else create
            existing = History.search([
                ('product_id', '=', product.id),
                ('week', '=', week),
                ('year', '=', year),
            ], limit=1)

            history_vals = {
                'product_id': product.id,
                'week': week,
                'year': year,
                'price_local': raw_price,
                'source': 'manual',
            }
            if existing:
                existing.write(history_vals)
            else:
                History.create(history_vals)

            saved_count += 1
            _logger.info(
                'Field buyer %s (%s) updated raw_price_crc for product %s [%d] to %.2f CRC',
                buyer.name, token[:6], product.name, product.id, raw_price,
            )

        if errors:
            error_msg = '; '.join(errors)
            return request.redirect(
                '/crfp/prices/%s?error=%s' % (token, request.env['ir.http']._slugify(error_msg))
            )

        _logger.info(
            'Field buyer %s saved %d prices for week %d/%d',
            buyer.name, saved_count, week, year,
        )

        if saved_count > 0:
            try:
                settings = request.env['crfp.settings'].sudo().get_settings()
                notify_partners = settings.field_price_notify_partner_ids
                if notify_partners:
                    request.env['res.partner'].sudo().message_notify(
                        partner_ids=notify_partners.ids,
                        subject='Precios de campo actualizados — Semana %d/%d' % (week, year),
                        body=(
                            '<p><b>%s</b> actualizó %d precio(s) de campo para la semana %d/%d.</p>'
                            % (buyer.name, saved_count, week, year)
                        ),
                        subtype_xmlid='mail.mt_comment',
                    )
            except Exception:
                _logger.exception('Failed to send field price update notification')

        return request.redirect('/crfp/prices/%s?success=1' % token)
