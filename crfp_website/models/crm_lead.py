"""
CRM Lead extension for CR Farm Website.

Adds AI-powered lead classification fields and methods.
Classification calls the Anthropic Claude API to determine:
  - Priority (high / medium / low)
  - Product interest category
  - Market region
  - One-sentence summary

API key stored in ir.config_parameter:
  key = crfp_website.anthropic_api_key
"""
import json
import logging

from odoo import models, fields, api

_logger = logging.getLogger(__name__)

# Claude model to use for classification (fast, cost-efficient)
_CLASSIFY_MODEL = 'claude-haiku-4-5-20251001'
_ANTHROPIC_API_URL = 'https://api.anthropic.com/v1/messages'

_CLASSIFY_SYSTEM = """You are a sales analyst for CR Farm Products (CR Farm), a Costa Rican agricultural export company.
CR Farm exports tropical root vegetables (yuca, ñame, malanga, taro, ginger, eddoes),
coconuts, sugar cane, and tropical vegetables to buyers in North America, Europe, and the Caribbean.

Your task: classify a new inbound lead.

Respond ONLY with a valid JSON object — no markdown, no extra text — with these exact keys:
{
  "priority": "high" | "medium" | "low",
  "product_interest": "tubers" | "coconut" | "sugar_cane" | "vegetables" | "mixed" | "unknown",
  "region": "north_america" | "europe" | "caribbean" | "central_america" | "south_america" | "other",
  "summary": "<one concise sentence describing this lead's business potential>"
}

Priority guide:
  high   = clear buyer intent, known importer, or large-volume signals
  medium = interested but vague, or small-scale buyer
  low    = general inquiry, student, journalist, or competitor
"""


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    # ── AI classification fields ──
    crfp_ai_priority = fields.Selection([
        ('high', 'Alto'),
        ('medium', 'Medio'),
        ('low', 'Bajo'),
    ], string='Prioridad IA', index=True)

    crfp_product_interest = fields.Selection([
        ('tubers', 'Raíces y Tubérculos'),
        ('coconut', 'Coco'),
        ('sugar_cane', 'Caña de Azúcar'),
        ('vegetables', 'Vegetales y Otros'),
        ('mixed', 'Mixto / Varios Productos'),
        ('unknown', 'Por determinar'),
    ], string='Producto de Interés (IA)')

    crfp_region = fields.Selection([
        ('north_america', 'Norteamérica'),
        ('europe', 'Europa'),
        ('caribbean', 'Caribe'),
        ('central_america', 'Centroamérica'),
        ('south_america', 'Suramérica'),
        ('other', 'Otro'),
    ], string='Región de Mercado (IA)')

    crfp_ai_classified = fields.Boolean(
        string='Clasificado por IA',
        default=False,
        help='Indicates that this lead has been classified by the AI engine',
    )
    crfp_ai_summary = fields.Text(
        string='Resumen IA',
        help='One-sentence AI summary of this lead\'s business potential',
    )
    crfp_from_website = fields.Boolean(
        string='Captado desde Website',
        default=False,
        help='True when the lead was submitted through the CR Farm website form',
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Public methods
    # ─────────────────────────────────────────────────────────────────────────

    def action_classify_with_ai(self):
        """Manual button action to (re)classify selected leads."""
        for lead in self:
            lead._classify_with_ai()

    def action_reset_ai_classification(self):
        """Clear AI classification so the cron will retry."""
        self.write({
            'crfp_ai_classified': False,
            'crfp_ai_priority': False,
            'crfp_product_interest': False,
            'crfp_region': False,
            'crfp_ai_summary': False,
        })

    # ─────────────────────────────────────────────────────────────────────────
    # Core AI classification
    # ─────────────────────────────────────────────────────────────────────────

    def _classify_with_ai(self):
        """Call Claude API to classify this lead. Updates fields in-place."""
        self.ensure_one()
        api_key = self._get_anthropic_api_key()
        if not api_key:
            _logger.warning('crfp_website: anthropic_api_key not configured — skipping AI classification')
            return

        prompt = self._build_classification_prompt()
        raw = self._call_anthropic(api_key, _CLASSIFY_MODEL, _CLASSIFY_SYSTEM, prompt, max_tokens=300)
        if not raw:
            return

        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            _logger.warning('crfp_website: could not parse AI classification response: %s', raw)
            return

        vals = {'crfp_ai_classified': True}
        if data.get('priority') in ('high', 'medium', 'low'):
            vals['crfp_ai_priority'] = data['priority']
        if data.get('product_interest') in ('tubers', 'coconut', 'sugar_cane', 'vegetables', 'mixed', 'unknown'):
            vals['crfp_product_interest'] = data['product_interest']
        if data.get('region') in ('north_america', 'europe', 'caribbean', 'central_america', 'south_america', 'other'):
            vals['crfp_region'] = data['region']
        if data.get('summary'):
            vals['crfp_ai_summary'] = str(data['summary'])[:512]

        self.sudo().write(vals)
        _logger.info('crfp_website: lead %s classified — priority=%s product=%s region=%s',
                     self.id, vals.get('crfp_ai_priority'), vals.get('crfp_product_interest'), vals.get('crfp_region'))

    def _build_classification_prompt(self):
        return (
            f"Name: {self.contact_name or self.partner_name or ''}\n"
            f"Company: {self.partner_name or ''}\n"
            f"Email: {self.email_from or ''}\n"
            f"Phone: {self.phone or ''}\n"
            f"Country: {self.country_id.name if self.country_id else ''}\n"
            f"Description / Message: {self.description or ''}\n"
            f"Lead title: {self.name or ''}"
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Cron entry point
    # ─────────────────────────────────────────────────────────────────────────

    @api.model
    def _cron_classify_unclassified_leads(self):
        """Scheduled action: classify website leads that have not been processed yet."""
        unclassified = self.search([
            ('crfp_from_website', '=', True),
            ('crfp_ai_classified', '=', False),
        ], limit=50)
        _logger.info('crfp_website: cron classifying %d unclassified leads', len(unclassified))
        for lead in unclassified:
            try:
                lead._classify_with_ai()
            except Exception:
                _logger.exception('crfp_website: error classifying lead %s', lead.id)

    # ─────────────────────────────────────────────────────────────────────────
    # Anthropic API helper (uses requests — no extra package needed)
    # ─────────────────────────────────────────────────────────────────────────

    def _get_anthropic_api_key(self):
        return self.env['ir.config_parameter'].sudo().get_param('crfp_website.anthropic_api_key', '')

    def _call_anthropic(self, api_key, model, system_prompt, user_message, max_tokens=1024):
        """
        Call the Anthropic Messages API via requests.
        Returns the text content of the first message block, or None on error.
        """
        try:
            import requests as req
        except ImportError:
            _logger.error('crfp_website: requests library not available')
            return None

        headers = {
            'x-api-key': api_key,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json',
        }
        payload = {
            'model': model,
            'max_tokens': max_tokens,
            'system': system_prompt,
            'messages': [{'role': 'user', 'content': user_message}],
        }
        try:
            resp = req.post(_ANTHROPIC_API_URL, headers=headers, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            content = data.get('content', [])
            if content and content[0].get('type') == 'text':
                return content[0]['text']
        except Exception:
            _logger.exception('crfp_website: Anthropic API call failed')
        return None
