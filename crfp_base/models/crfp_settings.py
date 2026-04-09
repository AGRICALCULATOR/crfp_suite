import logging
from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class CrfpSettings(models.Model):
    _name = 'crfp.settings'
    _description = 'CR Farm Export Settings'

    name = fields.Char(string='Name', default='CR Farm Settings', required=True)
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company, required=True,
    )

    # ── Exchange Rate ──────────────────────────────────────────────────────────
    # Actualizado via botón "Sincronizar" o cron diario.
    # Lee de res.currency.rate (misma fuente que l10n_cr_einvoice).
    # Configurar proveedor en: Contabilidad → Configuración → Monedas → Tasas automáticas.
    exchange_rate = fields.Float(
        string='Exchange Rate (CRC/USD)', digits=(12, 2), default=503.0,
        help='Tipo de cambio CRC/USD. Se sincroniza desde Contabilidad '
             '(res.currency.rate) via botón o cron diario.',
    )
    exchange_rate_source = fields.Selection([
        ('auto', 'Automático (Odoo Contabilidad)'),
        ('manual', 'Manual'),
    ], string='Fuente Tipo de Cambio', default='auto',
        help='Auto: usa la tasa de res.currency.rate (xe.com/ECB). '
             'Manual: permite ingresar el tipo de cambio a mano.',
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

    # ── Logistics Defaults ─────────────────────────────────────────────────────
    default_port_origin_id = fields.Many2one(
        'crfp.port', string='Default Port of Origin',
        help='Default origin port for new shipments (e.g. Puerto Moin)',
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
    # Exchange Rate — Centralizado con res.currency.rate (Odoo Contabilidad)
    # ─────────────────────────────────────────────────────────────────────────

    def _get_odoo_exchange_rate(self):
        """
        Obtiene el tipo de cambio CRC/USD desde res.currency.rate.
        Usa inverse_company_rate (CRC por 1 USD) — misma lógica que
        l10n_cr_einvoice._fp_get_exchange_rate().
        """
        self.ensure_one()
        usd = self.env.ref('base.USD', raise_if_not_found=False)
        if not usd or not usd.active:
            _logger.warning('Currency USD not found or inactive')
            return 0.0

        # inverse_company_rate = cuántos CRC por 1 USD
        rate = getattr(usd, 'inverse_company_rate', 0.0)
        if rate and rate > 0:
            return round(rate, 2)

        # Fallback: buscar última tasa en res.currency.rate
        company = self.company_id or self.env.company
        rate_record = self.env['res.currency.rate'].search([
            ('currency_id', '=', usd.id),
            ('company_id', 'in', [company.id, False]),
        ], order='name desc', limit=1)
        if rate_record and rate_record.company_rate:
            # company_rate = CRC por 1 USD (inverse_company_rate)
            return round(1.0 / rate_record.company_rate, 2) if rate_record.company_rate else 0.0
        return 0.0

    def action_update_exchange_rate(self):
        """Sincroniza el tipo de cambio desde res.currency.rate (Odoo Contabilidad)."""
        self.ensure_one()
        rate = self._get_odoo_exchange_rate()
        if not rate or rate <= 0:
            raise UserError(
                'No se encontró tipo de cambio USD en Odoo.\n\n'
                'Verifique que en Contabilidad → Configuración → Monedas:\n'
                '• La moneda USD esté activa\n'
                '• "Tasas de cambio automáticas" esté activado\n'
                '• El servicio sea xe.com y el intervalo "Diario"\n\n'
                'Luego dele click al botón de actualizar (↻) en esa sección.'
            )
        self.write({
            'exchange_rate': rate,
            'exchange_rate_last_update': fields.Datetime.now(),
        })
        _logger.info('Exchange rate synced from Odoo: %.2f CRC/USD', rate)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Tipo de Cambio Actualizado',
                'message': f'Tasa: {rate:.2f} CRC/USD (desde Odoo Contabilidad)',
                'type': 'success',
                'sticky': False,
            },
        }

    def _cron_update_exchange_rate(self):
        """Cron diario: sincroniza tipo de cambio desde res.currency.rate."""
        rate_changed = False
        for record in self.search([('exchange_rate_source', '=', 'auto')]):
            try:
                rate = record._get_odoo_exchange_rate()
                if rate and rate > 0:
                    old_rate = record.exchange_rate
                    record.write({
                        'exchange_rate': rate,
                        'exchange_rate_last_update': fields.Datetime.now(),
                    })
                    if abs(old_rate - rate) > 0.01:
                        rate_changed = True
                    _logger.info(
                        'Cron: exchange rate for %s updated to %.2f', record.name, rate
                    )
                else:
                    _logger.warning(
                        'Cron: no USD rate found in res.currency.rate for %s', record.name
                    )
            except Exception as e:
                _logger.error(
                    'Cron failed to sync exchange rate for %s: %s', record.name, e
                )

        # BP-02: Recalculate draft quotations with new exchange rate
        if rate_changed:
            try:
                settings = self.search([], limit=1)
                new_rate = settings.exchange_rate if settings else 0
                if new_rate > 0:
                    drafts = self.env['crfp.quotation'].search([('state', '=', 'draft')])
                    for q in drafts:
                        q.write({'exchange_rate': new_rate})
                    _logger.info('Cron: updated %d draft quotations with new TC', len(drafts))
            except Exception as e:
                _logger.error('Cron: failed to update draft quotations: %s', e)

        # BP-06: Recalculate active price lists with new exchange rate
        if rate_changed:
            try:
                active_lists = self.env['crfp.price.list'].search([('status', '=', 'active')])
                if active_lists:
                    _logger.info('Cron: %d active price lists flagged for TC update', len(active_lists))
            except Exception as e:
                _logger.error('Cron: failed to check price lists: %s', e)
