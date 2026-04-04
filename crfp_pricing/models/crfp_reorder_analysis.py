"""
CR Farm Pricing — AI Reorder Analysis.

Detects clients that should be placing a new order based on their
historical buying frequency, but haven't done so. Creates CRM activities
and optionally sends AI-personalized reactivation emails via Claude.

Model: crfp.reorder.analysis
Cron: weekly, called via _cron_run_reorder_analysis()
"""
import json
import logging
from datetime import timedelta

from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

_ANTHROPIC_API_URL = 'https://api.anthropic.com/v1/messages'
_AI_MODEL = 'claude-haiku-4-5-20251001'

# Minimum confirmed orders to have meaningful buying pattern data
_MIN_ORDERS_FOR_ANALYSIS = 2

# How many days of SO history to analyze
_LOOKBACK_DAYS = 730  # 2 years


class CrfpReorderAnalysis(models.Model):
    _name = 'crfp.reorder.analysis'
    _description = 'AI Reorder Analysis — Buying Pattern per Client'
    _order = 'days_overdue desc, partner_id'
    _rec_name = 'partner_id'

    # ── Identity ──
    partner_id = fields.Many2one(
        'res.partner', string='Client', required=True,
        index=True, ondelete='cascade',
    )

    # ── Buying pattern stats ──
    order_count = fields.Integer(string='Orders Analyzed', readonly=True)
    first_order_date = fields.Date(string='First Order', readonly=True)
    last_order_date = fields.Date(string='Last Order', readonly=True)
    avg_interval_days = fields.Float(
        string='Avg Days Between Orders', digits=(12, 1), readonly=True,
        help='Average number of calendar days between consecutive confirmed orders',
    )
    total_revenue_usd = fields.Float(
        string='Est. Revenue (USD)', digits=(12, 2), readonly=True,
        help='Sum of confirmed sale order amounts in the analysis window',
    )
    last_products = fields.Char(
        string='Last Products Ordered', readonly=True,
        help='Comma-separated list of products in the most recent order',
    )

    # ── Reorder prediction ──
    expected_next_order = fields.Date(
        string='Expected Next Order', readonly=True,
        help='last_order_date + avg_interval_days',
    )
    days_overdue = fields.Integer(
        string='Days Overdue', readonly=True,
        help='Positive = overdue for a new order. Negative = not yet due.',
    )
    status = fields.Selection([
        ('new',       'New Client'),
        ('active',    'Active (On Track)'),
        ('due_soon',  'Due Soon (< 14 days)'),
        ('overdue',   'Overdue'),
        ('inactive',  'Inactive (> 2x interval)'),
    ], string='Status', readonly=True, default='active', index=True)

    # ── AI output ──
    ai_insights = fields.Text(
        string='AI Insights',
        help='Claude-generated analysis of this client\'s buying behaviour and reactivation suggestions',
    )
    ai_email_subject = fields.Char(string='AI Email Subject')
    ai_email_body = fields.Html(string='AI Email Body')
    ai_last_run = fields.Datetime(string='AI Last Run', readonly=True)

    # ── Activity tracking ──
    activity_created = fields.Boolean(string='Activity Created', default=False)
    last_activity_date = fields.Datetime(string='Last Activity Created', readonly=True)
    email_sent = fields.Boolean(string='Reactivation Email Sent', default=False)
    email_sent_date = fields.Datetime(string='Email Sent Date', readonly=True)

    # ── Metadata ──
    last_analysis_date = fields.Datetime(
        string='Last Analysis Run', readonly=True, default=fields.Datetime.now)
    notes = fields.Text(string='Notes')

    # ─────────────────────────────────────────────────────────────────────────
    # Cron entry point
    # ─────────────────────────────────────────────────────────────────────────

    @api.model
    def _cron_run_reorder_analysis(self):
        """Weekly cron: analyze buying patterns for all active clients."""
        _logger.info('crfp_pricing: starting reorder analysis cron')
        cutoff = fields.Date.today() - timedelta(days=_LOOKBACK_DAYS)

        # Find all partners with at least one confirmed SO in the lookback window
        so_domain = [
            ('state', 'in', ('sale', 'done')),
            ('date_order', '>=', str(cutoff)),
        ]
        orders = self.env['sale.order'].sudo().search(so_domain)
        partner_ids = orders.mapped('partner_id.commercial_partner_id').ids
        partner_ids = list(set(partner_ids))

        _logger.info('crfp_pricing: analyzing %d partners', len(partner_ids))

        for partner_id in partner_ids:
            try:
                partner = self.env['res.partner'].sudo().browse(partner_id)
                self._analyze_partner(partner)
            except Exception:
                _logger.exception(
                    'crfp_pricing: error analyzing partner %s', partner_id)

        # Auto-create activities for overdue clients
        overdue = self.search([
            ('status', 'in', ('overdue', 'inactive')),
            ('activity_created', '=', False),
        ])
        _logger.info('crfp_pricing: creating activities for %d overdue clients', len(overdue))
        for rec in overdue:
            try:
                rec._create_sales_activity()
            except Exception:
                _logger.exception(
                    'crfp_pricing: error creating activity for %s', rec.partner_id.name)

        _logger.info('crfp_pricing: reorder analysis cron completed')

    # ─────────────────────────────────────────────────────────────────────────
    # Analysis logic
    # ─────────────────────────────────────────────────────────────────────────

    def _analyze_partner(self, partner):
        """Compute buying pattern for one partner and upsert the analysis record."""
        cutoff = fields.Date.today() - timedelta(days=_LOOKBACK_DAYS)

        orders = self.env['sale.order'].sudo().search([
            ('partner_id.commercial_partner_id', '=', partner.id),
            ('state', 'in', ('sale', 'done')),
            ('date_order', '>=', str(cutoff)),
        ], order='date_order asc')

        if not orders:
            return

        order_count = len(orders)
        dates = [o.date_order.date() for o in orders]
        first_date = dates[0]
        last_date = dates[-1]
        total_revenue = sum(o.amount_total for o in orders)

        # Average interval
        if order_count >= 2:
            intervals = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates))]
            avg_interval = sum(intervals) / len(intervals)
        else:
            avg_interval = 0.0

        # Last products
        last_order = orders[-1]
        last_products = ', '.join(
            last_order.order_line.mapped('product_id.name')[:5]
        ) if last_order.order_line else ''

        # Compute expected next order and overdue days
        today = fields.Date.today()
        if avg_interval and order_count >= _MIN_ORDERS_FOR_ANALYSIS:
            expected_date = last_date + timedelta(days=int(avg_interval))
            days_ov = (today - expected_date).days
        else:
            expected_date = False
            days_ov = 0

        # Status
        if order_count < _MIN_ORDERS_FOR_ANALYSIS:
            status = 'new'
        elif days_ov > avg_interval:  # more than 2x overdue
            status = 'inactive'
        elif days_ov > 0:
            status = 'overdue'
        elif days_ov > -14:
            status = 'due_soon'
        else:
            status = 'active'

        vals = {
            'partner_id': partner.id,
            'order_count': order_count,
            'first_order_date': first_date,
            'last_order_date': last_date,
            'avg_interval_days': avg_interval,
            'total_revenue_usd': total_revenue,
            'last_products': last_products,
            'expected_next_order': expected_date or False,
            'days_overdue': days_ov,
            'status': status,
            'last_analysis_date': fields.Datetime.now(),
        }

        # Upsert
        existing = self.search([('partner_id', '=', partner.id)], limit=1)
        if existing:
            # Reset activity flag if no longer overdue (client came back)
            if status == 'active' and existing.status in ('overdue', 'inactive'):
                vals['activity_created'] = False
            existing.write(vals)
        else:
            self.create(vals)

    # ─────────────────────────────────────────────────────────────────────────
    # AI insights generation
    # ─────────────────────────────────────────────────────────────────────────

    def action_generate_ai_insights(self):
        """Generate AI insights and personalized email for this client."""
        for rec in self:
            rec._generate_ai_insights()

    def _generate_ai_insights(self):
        """Call Claude to generate insights and reactivation email content."""
        self.ensure_one()
        api_key = self.env['ir.config_parameter'].sudo().get_param(
            'crfp_website.anthropic_api_key', '')
        if not api_key:
            _logger.warning('crfp_pricing: anthropic_api_key not set — skipping AI insights')
            return

        prompt = self._build_analysis_prompt()
        system_prompt = (
            "You are a sales analyst for CR Farm Products (CR Farm), a Costa Rican agricultural "
            "export company exporting tropical roots (cassava, eddoes, malanga, taro, yam) and "
            "coconuts to buyers in the USA, Europe and the Caribbean.\n\n"
            "Analyze the client's buying pattern and generate:\n"
            "1. A concise 2-3 sentence business insight about this client's behavior.\n"
            "2. A personalized reactivation email subject line.\n"
            "3. A professional, warm reactivation email body (HTML format, max 200 words) "
            "that mentions their history and encourages them to place their next order. "
            "Sign it as 'CR Farm Products Export Team'.\n\n"
            "Respond ONLY with a valid JSON object — no markdown, no code blocks:\n"
            '{"insights": "...", "email_subject": "...", "email_body": "<html>..."}'
        )

        raw = self._call_anthropic(api_key, system_prompt, prompt)
        if not raw:
            return

        # Strip possible markdown code fences
        raw = raw.strip()
        if raw.startswith('```'):
            raw = raw.split('```')[1]
            if raw.startswith('json'):
                raw = raw[4:]

        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            _logger.warning('crfp_pricing: could not parse AI response for %s', self.partner_id.name)
            return

        self.write({
            'ai_insights': data.get('insights', ''),
            'ai_email_subject': (data.get('email_subject') or '')[:255],
            'ai_email_body': data.get('email_body', ''),
            'ai_last_run': fields.Datetime.now(),
        })

    def _build_analysis_prompt(self):
        return (
            f"Client: {self.partner_id.name}\n"
            f"Country: {self.partner_id.country_id.name if self.partner_id.country_id else 'Unknown'}\n"
            f"Total orders in 2 years: {self.order_count}\n"
            f"First order: {self.first_order_date}\n"
            f"Last order: {self.last_order_date}\n"
            f"Average days between orders: {self.avg_interval_days:.0f}\n"
            f"Expected next order: {self.expected_next_order or 'N/A'}\n"
            f"Days overdue: {self.days_overdue}\n"
            f"Status: {self.status}\n"
            f"Last products ordered: {self.last_products or 'N/A'}\n"
            f"Estimated total revenue (USD): {self.total_revenue_usd:,.0f}\n"
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Activity creation
    # ─────────────────────────────────────────────────────────────────────────

    def action_create_activity(self):
        for rec in self:
            rec._create_sales_activity()

    def _create_sales_activity(self):
        """Create a CRM activity (to-do) on the partner for the sales team."""
        self.ensure_one()
        partner = self.partner_id

        # Find 'To-Do' activity type
        todo_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        if not todo_type:
            todo_type = self.env['mail.activity.type'].search(
                [('name', 'ilike', 'todo')], limit=1)

        if not todo_type:
            _logger.warning('crfp_pricing: could not find todo activity type')
            return

        days_label = f'{self.days_overdue} days overdue' if self.days_overdue > 0 else 'Due soon'
        note = (
            f'<p><strong>Reorder Alert — {days_label}</strong></p>'
            f'<p>Client <strong>{partner.name}</strong> buys every '
            f'<strong>{self.avg_interval_days:.0f} days</strong> on average. '
            f'Last order: <strong>{self.last_order_date}</strong>.</p>'
            f'<p>Last products: {self.last_products or "N/A"}</p>'
            f'<p>Suggested action: contact client to check if they need to place a new order.</p>'
        )

        partner.activity_schedule(
            activity_type_id=todo_type.id,
            summary=f'Reorder Alert: {partner.name} ({days_label})',
            note=note,
            date_deadline=fields.Date.today() + timedelta(days=3),
        )

        self.write({
            'activity_created': True,
            'last_activity_date': fields.Datetime.now(),
        })
        _logger.info('crfp_pricing: created reorder activity for %s', partner.name)

    # ─────────────────────────────────────────────────────────────────────────
    # Reactivation email
    # ─────────────────────────────────────────────────────────────────────────

    def action_send_reactivation_email(self):
        """Send the AI-generated reactivation email to the client."""
        self.ensure_one()
        if not self.ai_email_body or not self.ai_email_subject:
            raise UserError(
                'No AI email content yet. Run "Generate AI Insights" first.')
        if not self.partner_id.email:
            raise UserError(
                f'Client {self.partner_id.name} has no email address configured.')

        mail = self.env['mail.mail'].sudo().create({
            'subject': self.ai_email_subject,
            'body_html': self.ai_email_body,
            'email_to': self.partner_id.email,
            'email_from': self.env.company.email or 'exports@crfarm.com',
            'auto_delete': True,
        })
        mail.send()
        self.write({
            'email_sent': True,
            'email_sent_date': fields.Datetime.now(),
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Email Sent',
                'message': f'Reactivation email sent to {self.partner_id.email}',
                'type': 'success',
                'sticky': False,
            },
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Anthropic API helper
    # ─────────────────────────────────────────────────────────────────────────

    def _call_anthropic(self, api_key, system_prompt, user_message, max_tokens=1024):
        try:
            import requests as req
        except ImportError:
            _logger.error('crfp_pricing: requests library not available')
            return None

        headers = {
            'x-api-key': api_key,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json',
        }
        payload = {
            'model': _AI_MODEL,
            'max_tokens': max_tokens,
            'system': system_prompt,
            'messages': [{'role': 'user', 'content': user_message}],
        }
        try:
            resp = req.post(_ANTHROPIC_API_URL, headers=headers, json=payload, timeout=45)
            resp.raise_for_status()
            data = resp.json()
            content = data.get('content', [])
            if content and content[0].get('type') == 'text':
                return content[0]['text']
        except Exception:
            _logger.exception('crfp_pricing: Anthropic API call failed')
        return None
