"""
CR Farm Logistics — Customer Portal Controller.

Routes
------
GET  /my/crfarm-shipments                     List of partner's shipments
GET  /my/crfarm-shipments/<id>                Detail view of one shipment
GET  /my/crfarm-shipments/<id>/attachment/<a> Download a document attachment
"""
import logging

from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager

_logger = logging.getLogger(__name__)

# States the client can actually see (no draft)
_PORTAL_STATES = [
    'space_requested', 'booking_requested', 'booking_confirmed',
    'si_sent', 'bl_draft_received', 'loading', 'docs_final',
    'shipped', 'in_transit', 'arrived', 'delivered', 'closed',
]

_STATE_LABELS = {
    'draft': 'Draft',
    'space_requested': 'Space Requested',
    'booking_requested': 'Booking Requested',
    'booking_confirmed': 'Booking Confirmed',
    'si_sent': 'SI Sent',
    'bl_draft_received': 'BL Draft Received',
    'loading': 'Loading',
    'docs_final': 'Documents Ready',
    'shipped': 'Shipped',
    'in_transit': 'In Transit',
    'arrived': 'Arrived',
    'delivered': 'Delivered',
    'closed': 'Closed',
    'cancelled': 'Cancelled',
}

_STATE_COLORS = {
    'draft': 'secondary',
    'space_requested': 'info',
    'booking_requested': 'info',
    'booking_confirmed': 'primary',
    'si_sent': 'primary',
    'bl_draft_received': 'primary',
    'loading': 'warning',
    'docs_final': 'warning',
    'shipped': 'success',
    'in_transit': 'success',
    'arrived': 'success',
    'delivered': 'success',
    'closed': 'secondary',
    'cancelled': 'danger',
}


class CrfarmShipmentPortal(CustomerPortal):

    # ── Portal home counter ──────────────────────────────────────────────────

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'crfarm_shipment_count' in counters:
            values['crfarm_shipment_count'] = request.env['crfp.shipment'].sudo().search_count(
                self._get_shipment_domain()
            )
        return values

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _get_shipment_domain(self):
        partner = request.env.user.partner_id
        return [
            ('partner_id', 'in', [partner.id] + partner.child_ids.ids),
            ('state', 'in', _PORTAL_STATES),
        ]

    def _shipment_get_page_view_values(self, shipment, **kwargs):
        return {
            'shipment': shipment,
            'state_label': _STATE_LABELS.get(shipment.state, shipment.state),
            'state_color': _STATE_COLORS.get(shipment.state, 'secondary'),
            'state_labels': _STATE_LABELS,
            'state_colors': _STATE_COLORS,
            'page_name': 'crfarm_shipment',
        }

    # ── Routes ───────────────────────────────────────────────────────────────

    @http.route(
        '/my/crfarm-shipments',
        type='http', auth='user', website=True,
    )
    def portal_shipments(self, page=1, sortby='date_desc', **kw):
        domain = self._get_shipment_domain()
        Shipment = request.env['crfp.shipment'].sudo()

        sortby_options = {
            'date_desc': ('create_date desc', 'Newest First'),
            'date_asc': ('create_date asc', 'Oldest First'),
            'state': ('state asc', 'Status'),
            'eta': ('eta asc', 'ETA'),
        }
        order, sort_label = sortby_options.get(sortby, sortby_options['date_desc'])

        shipment_count = Shipment.search_count(domain)
        per_page = 12
        pager = portal_pager(
            url='/my/crfarm-shipments',
            url_args={'sortby': sortby},
            total=shipment_count,
            page=page,
            step=per_page,
        )
        shipments = Shipment.search(
            domain, order=order,
            limit=per_page, offset=pager['offset'],
        )

        return request.render('crfp_logistics.portal_shipments_list', {
            'shipments': shipments,
            'pager': pager,
            'sortby': sortby,
            'sortby_options': sortby_options,
            'state_labels': _STATE_LABELS,
            'state_colors': _STATE_COLORS,
            'page_name': 'crfarm_shipments',
        })

    @http.route(
        '/my/crfarm-shipments/<int:shipment_id>',
        type='http', auth='user', website=True,
    )
    def portal_shipment_detail(self, shipment_id, **kw):
        partner = request.env.user.partner_id
        allowed_partners = [partner.id] + partner.child_ids.ids

        shipment = request.env['crfp.shipment'].sudo().browse(shipment_id)
        if not shipment.exists() or shipment.partner_id.id not in allowed_partners:
            return request.not_found()

        # Only portal-visible states
        if shipment.state not in _PORTAL_STATES:
            return request.not_found()

        # Only show documents that are ready/approved (not internal pending docs)
        portal_docs = shipment.document_ids.filtered(
            lambda d: d.state in ('ready', 'sent', 'received', 'approved')
            and d.attachment_ids
        )

        values = self._shipment_get_page_view_values(shipment)
        values['portal_docs'] = portal_docs
        return request.render('crfp_logistics.portal_shipment_detail', values)

    @http.route(
        '/my/crfarm-shipments/<int:shipment_id>/attachment/<int:attachment_id>',
        type='http', auth='user',
    )
    def portal_shipment_attachment(self, shipment_id, attachment_id, **kw):
        """Serve a document attachment after verifying access."""
        partner = request.env.user.partner_id
        allowed_partners = [partner.id] + partner.child_ids.ids

        shipment = request.env['crfp.shipment'].sudo().browse(shipment_id)
        if not shipment.exists() or shipment.partner_id.id not in allowed_partners:
            return request.not_found()

        # Verify the attachment belongs to a ready document on this shipment
        portal_docs = shipment.document_ids.filtered(
            lambda d: d.state in ('ready', 'sent', 'received', 'approved')
        )
        attachment_in_doc = any(
            attachment_id in doc.attachment_ids.ids for doc in portal_docs
        )
        if not attachment_in_doc:
            return request.not_found()

        attachment = request.env['ir.attachment'].sudo().browse(attachment_id)
        if not attachment.exists():
            return request.not_found()

        try:
            stream = request.env['ir.binary']._get_stream_from(attachment)
            return stream.get_response(as_attachment=True)
        except Exception:
            _logger.exception('crfp_logistics portal: error serving attachment %s', attachment_id)
            return request.not_found()
