import logging
import requests
import xml.etree.ElementTree as ET
from datetime import date
from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# BCCR public API — indicator 318 = USD sell rate (tipo de cambio venta)
_BCCR_URL = (
    'https://gee.bccr.fi.cr/Indicadores/Suscripciones/WS/'
    'wsindicadoreseconomicos.asmx/ObtenerIndicadoresEconomicosXML'
)
_BCCR_INDICATOR = '318'


class CrfpSettings(models.Model):
    _name = 'crfp.settings'
    _description = 'CR Farm Export Settings'

    name = fields.Char(string='Name', default='CR Farm Settings', required=True)
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company, required=True,
    )

    # ── Exchange Rate ──────────────────────────────────────────────────────────
    exchange_rate = fields.Float(
        string='Exchange Rate (CRC/USD)', default=503.0, digits=(12, 2),
        help='Costa Rican Colon to US Dollar exchange rate (sell rate)',
    )
    exchange_rate_auto = fields.Boolean(
        string='Auto-Update from BCCR', default=False,
        help='Automatically fetch the exchange rate from BCCR every day',
    )
    exchange_rate_last_update = fields.Datetime(
        string='Last Update', readonly=True,
    )

    # ── Container & Box Defaults ───────────────────────────────────────────────
    default_total_boxes = fields.Integer(
        string='Default Boxes per Container', default=1386,
        help='Default number of boxes in a full container (used in calculator)',
    )
    default_boxes_per_pallet = fields.Integer(
        string='Default Boxes per Pallet', default=66,
    )

    # ── Default Fixed Costs (snapshot defaults for new quotations) ─────────────
    fc_transport_default = fields.Float(
        string='Transport (USD)', default=600.0, digits=(12, 2),
        help='Default inland transport cost loaded into new quotations',
    )
    fc_thc_origin_default = fields.Float(
        string='THC Origin (USD)', default=380.0, digits=(12, 2),
        help='Terminal handling charge at origin',
    )
    fc_fumigation_default = fields.Float(
        string='Fumigation Origin (USD)', default=180.0, digits=(12, 2),
    )
    fc_broker_default = fields.Float(
        string='Broker / Customs (USD)', default=150.0, digits=(12, 2),
    )
    fc_thc_dest_default = fields.Float(
        string='THC Destination (USD)', default=0.0, digits=(12, 2),
    )
    fc_fumig_dest_default = fields.Float(
        string='Fumigation Destination (USD)', default=0.0, digits=(12, 2),
    )
    fc_inland_dest_default = fields.Float(
        string='Inland Destination (USD)', default=0.0, digits=(12, 2),
    )
    fc_insurance_pct_default = fields.Float(
        string='Insurance (%)', default=0.30, digits=(12, 2),
        help='Insurance as percentage of FOB value',
    )
    fc_duties_pct_default = fields.Float(
        string='Duties (%)', default=0.0, digits=(12, 2),
    )

    # ── Quality / Monitoring ───────────────────────────────────────────────────
    temperature_tolerance = fields.Float(
        string='Temperature Tolerance (°C)', default=2.0, digits=(12, 1),
        help='Reefer temperature tolerance for alerts',
    )
    price_validity_days = fields.Integer(
        string='Price Validity (Days)', default=7,
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Singleton constraint — one settings record per company
    # ─────────────────────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        """Enforce singleton: only one settings record per company."""
        for vals in vals_list:
            company_id = vals.get('company_id', self.env.company.id)
            existing = self.search([('company_id', '=', company_id)], limit=1)
            if existing:
                raise UserError(
                    'A settings record already exists for this company (ID=%d). '
                    'Please edit the existing record instead of creating a new one.'
                    % existing.id
                )
        return super().create(vals_list)

    # ─────────────────────────────────────────────────────────────────────────
    # Singleton accessor
    # ─────────────────────────────────────────────────────────────────────────

    @api.model
    def get_settings(self, company_id=None):
        """Return the settings record for the current company; create if missing."""
        domain = [('company_id', '=', company_id or self.env.company.id)]
        record = self.search(domain, limit=1)
        if not record:
            record = self.create({'company_id': company_id or self.env.company.id})
        return record

    # ─────────────────────────────────────────────────────────────────────────
    # BCCR Exchange Rate
    # ─────────────────────────────────────────────────────────────────────────

    def action_update_exchange_rate(self):
        """Fetch today's USD sell rate from the BCCR public API and store it."""
        self.ensure_one()
        today_str = date.today().strftime('%d/%m/%Y')
        params = {
            'Indicador': _BCCR_INDICATOR,
            'FechaInicio': today_str,
            'FechaFinal': today_str,
            'Nombre': 'CRFARM',
            'SubNiveles': 'N',
            'CorreoElectronico': '',
            'Token': '',
        }
        try:
            resp = requests.get(_BCCR_URL, params=params, timeout=10)
            resp.raise_for_status()
            rate = self._parse_bccr_response(resp.text)
        except requests.RequestException as e:
            _logger.error('BCCR API request failed: %s', e)
            raise UserError(
                f'Could not connect to BCCR API: {e}\n'
                'The exchange rate was NOT updated. Please try again or enter it manually.'
            )

        if not rate:
            raise UserError(
                'BCCR returned no exchange rate for today. '
                'The market may be closed. Please update manually.'
            )

        self.write({
            'exchange_rate': rate,
            'exchange_rate_last_update': fields.Datetime.now(),
        })
        _logger.info('BCCR exchange rate updated to %.2f CRC/USD', rate)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Exchange Rate Updated',
                'message': f'New rate: {rate:.2f} CRC/USD (BCCR sell rate)',
                'type': 'success',
                'sticky': False,
            },
        }

    @staticmethod
    def _parse_bccr_response(xml_text):
        """Parse BCCR XML response and return the float rate, or None."""
        try:
            root = ET.fromstring(xml_text)
            # The value lives in NUM_VALOR inside any nested element
            for elem in root.iter('NUM_VALOR'):
                text = (elem.text or '').strip()
                if text:
                    return float(text.replace(',', '.'))
        except Exception as e:
            _logger.warning('Could not parse BCCR response: %s', e)
        return None

    def _cron_update_exchange_rate(self):
        """Daily cron: update exchange rate for all settings with auto-update enabled."""
        for record in self.search([('exchange_rate_auto', '=', True)]):
            try:
                record.action_update_exchange_rate()
            except Exception as e:
                _logger.error(
                    'Cron failed to update exchange rate for %s: %s', record.name, e
                )
