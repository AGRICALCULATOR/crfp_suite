from odoo import models, fields, api
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)


class CrfpSettings(models.Model):
    _name = 'crfp.settings'
    _description = 'CR Farm Export Settings'

    name = fields.Char(
        string='Name',
        default='CR Farm Settings',
        required=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )

    # Exchange Rate Configuration
    exchange_rate = fields.Float(
        string='Exchange Rate (CRC/USD)',
        default=503.0,
        digits=(12, 2),
        help='Costa Rican Colon to US Dollar exchange rate'
    )
    exchange_rate_auto = fields.Boolean(
        string='Auto-Update Exchange Rate',
        default=False,
        help='Automatically update exchange rate from BCCR API'
    )
    exchange_rate_last_update = fields.Datetime(
        string='Last Exchange Rate Update',
        readonly=True,
        help='Timestamp of last successful exchange rate update'
    )

    # Container and Box Configuration
    default_total_boxes = fields.Integer(
        string='Default Boxes per Container',
        default=1386,
        help='Default number of boxes in a full container'
    )
    default_boxes_per_pallet = fields.Integer(
        string='Default Boxes per Pallet',
        default=66,
        help='Standard number of boxes per pallet'
    )

    # Temperature Monitoring
    temperature_tolerance = fields.Float(
        string='Temperature Tolerance (C)',
        default=2.0,
        digits=(12, 1),
        help='Temperature tolerance in Celsius for reefer container alerts'
    )

    # Quotation Configuration
    price_validity_days = fields.Integer(
        string='Price Validity (Days)',
        default=7,
        help='Number of days a quotation price is valid'
    )

    @api.model
    def get_settings(self, company_id=None):
        """
        Return the settings record for the given company (or current).
        Creates a new record if none exists.
        """
        domain = [('company_id', '=', company_id or self.env.company.id)]
        record = self.search(domain, limit=1)
        if not record:
            record = self.create({
                'company_id': company_id or self.env.company.id,
            })
        return record

    def action_update_exchange_rate(self):
        """
        Attempt to fetch and update the exchange rate from BCCR API.
        BCCR (Banco Central de Costa Rica) provides live exchange rates.

        Note: Actual API implementation pending configuration.
        Currently logs a placeholder message.
        """
        self.ensure_one()

        try:
            # TODO: Implement actual BCCR API call
            # BCCR API endpoint: https://gee.bccr.fi.cr/indicadoreseconomicos/
            # Indicator code for sell rate (venta) is 318

            _logger.warning(
                "Exchange rate update requested for %s but BCCR API integration "
                "is not yet configured. Please implement the API call.",
                self.name
            )

        except Exception as e:
            _logger.error(
                "Error updating exchange rate for %s: %s",
                self.name,
                str(e)
            )
            raise

    def _cron_update_exchange_rate(self):
        """
        Scheduled cron job to update exchange rates if auto-update is enabled.
        Called daily by scheduled action.
        """
        settings_records = self.search([('exchange_rate_auto', '=', True)])
        for record in settings_records:
            try:
                record.action_update_exchange_rate()
            except Exception as e:
                _logger.error(
                    "Cron job failed to update exchange rate for %s: %s",
                    record.name,
                    str(e)
                )
