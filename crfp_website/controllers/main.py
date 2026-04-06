"""
CR Farm Website — main HTTP controller.

NOTE: Public marketing pages are managed via the Odoo Website Builder.
This controller only handles the B2B lead submission that triggers AI
classification in crm.lead._classify_with_ai().
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
