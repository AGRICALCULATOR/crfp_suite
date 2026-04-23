import logging

import requests

from odoo import fields, models

_logger = logging.getLogger(__name__)


class ResCurrency(models.Model):
    _inherit = 'res.currency'

    def _upsert_company_inverse_rate(self, currency, company, inverse_rate):
        """Crea o actualiza la tasa de la fecha de hoy para una compañía."""
        company_currency = self.env['res.currency.rate'].sudo().search(
            [
                ('currency_id', '=', currency.id),
                ('company_id', '=', company.id),
                ('name', '=', fields.Date.context_today(self)),
            ],
            limit=1,
        )

        values = {
            'currency_id': currency.id,
            'company_id': company.id,
            'name': fields.Date.context_today(self),
            'inverse_company_rate': inverse_rate,
        }
        if company_currency:
            company_currency.write({'inverse_company_rate': inverse_rate})
            return company_currency

        return self.env['res.currency.rate'].sudo().create(values)

    def _update_hacienda_rates(self):
        """Consulta Hacienda y actualiza USD/EUR para compañías habilitadas."""
        params = self.env['ir.config_parameter'].sudo()
        auto_update = params.get_param('tipos_cambio_bccr.hacienda_rate_auto_update', 'True') == 'True'
        if not auto_update:
            _logger.info('Hacienda: actualización automática desactivada en configuración')
            return True

        companies = self.env['res.company'].sudo().search([])
        if not companies:
            _logger.info('Hacienda: no hay compañías disponibles para actualizar')
            return True

        target_currencies = {
            'USD': {
                'url': 'https://api.hacienda.go.cr/indicadores/tc/dolar',
                'extract': lambda payload: payload.get('venta', {}).get('valor'),
            },
            'EUR': {
                'url': 'https://api.hacienda.go.cr/indicadores/tc/euro',
                'extract': lambda payload: payload.get('colones'),
            },
        }

        rates = {}
        for code, conf in target_currencies.items():
            try:
                response = requests.get(conf['url'], timeout=10)
                response.raise_for_status()
                value = conf['extract'](response.json())
                if not value:
                    _logger.warning('Hacienda: no se encontró valor válido para %s', code)
                    continue
                rates[code] = float(value)
            except Exception as exc:
                _logger.error('Hacienda: error consultando %s: %s', code, exc)

        if not rates:
            return True

        now = fields.Datetime.now()
        for code, rate_value in rates.items():
            currency = self.search([('name', '=', code)], limit=1)
            if not currency:
                _logger.warning('Hacienda: no existe la moneda %s en esta base', code)
                continue

            for company in companies:
                self._upsert_company_inverse_rate(currency, company, rate_value)

            _logger.info('Hacienda: %s actualizado a %s en %s compañías', code, rate_value, len(companies))

        params.set_param('tipos_cambio_bccr.hacienda_rate_last_sync', fields.Datetime.to_string(now))
        return True
