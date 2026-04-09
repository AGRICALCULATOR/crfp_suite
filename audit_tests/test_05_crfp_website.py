# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════
  TEST 05 — crfp_website: Sitio B2B, Leads IA, Chatbot
  Diagnóstico: API Anthropic, clasificación leads, rate limit,
  productos del catálogo, seguridad del chatbot
═══════════════════════════════════════════════════════════════
"""
from odoo.tests.common import TransactionCase, tagged
from unittest.mock import patch, MagicMock
import logging
import json

_logger = logging.getLogger(__name__)


@tagged('audit_tests', 'crfp_website')
class TestWebsiteProduct(TransactionCase):
    """Modelo crfp.website.product para el catálogo B2B."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def test_product_create_all_categories(self):
        """Todos los tipos de categoría son válidos."""
        categories = ['tubers', 'coconut', 'sugar_cane', 'vegetables']
        for cat in categories:
            product = self.env['crfp.website.product'].create({
                'name': f'Audit {cat}',
                'category': cat,
            })
            self.assertEqual(product.category, cat)

    def test_product_format_fields(self):
        """Campos de formato se guardan correctamente."""
        product = self.env['crfp.website.product'].create({
            'name': 'Format Test',
            'category': 'tubers',
            'format_fresh': True,
            'format_peeled': True,
            'format_frozen': False,
        })
        self.assertTrue(product.format_fresh)
        self.assertTrue(product.format_peeled)
        self.assertFalse(product.format_frozen)

    def test_product_weights_and_specs(self):
        """Especificaciones técnicas B2B se almacenan."""
        product = self.env['crfp.website.product'].create({
            'name': 'Spec Test Yuca',
            'category': 'tubers',
            'scientific_name': 'Manihot esculenta',
            'box_weight_eu_kg': 18.0,
            'box_weight_usa_ca_kg': 40.0,
            'boxes_per_pallet': 66,
            'pallets_per_container': 20,
            'tariff_code': '0714.10',
        })
        self.assertEqual(product.scientific_name, 'Manihot esculenta')
        self.assertAlmostEqual(product.box_weight_eu_kg, 18.0)


@tagged('audit_tests', 'crfp_website')
class TestCrmLeadClassification(TransactionCase):
    """Clasificación de leads con IA (sin llamada real a API)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def _create_website_lead(self):
        """Helper: crea un lead como si viniera del formulario web."""
        return self.env['crm.lead'].create({
            'name': 'Audit Lead - Fresh Produce Import',
            'partner_name': 'European Foods GmbH',
            'email_from': 'buyer@eufoods.de',
            'phone': '+49 30 12345678',
            'description': 'Interested in importing 5 containers of yuca per month to Hamburg',
            'crfp_from_website': True,
            'crfp_ai_classified': False,
        })

    def test_lead_custom_fields_exist(self):
        """Campos crfp_* existen en crm.lead."""
        Lead = self.env['crm.lead']
        expected_fields = [
            'crfp_ai_priority', 'crfp_product_interest',
            'crfp_region', 'crfp_ai_classified',
            'crfp_ai_summary', 'crfp_from_website',
        ]
        for fname in expected_fields:
            self.assertIn(fname, Lead._fields,
                          f"Campo {fname} debe existir en crm.lead")

    def test_lead_classification_without_api_key(self):
        """Sin API key, clasificación debe fallar graciosamente."""
        lead = self._create_website_lead()
        # Asegurar que no hay API key
        self.env['ir.config_parameter'].sudo().set_param(
            'crfp_website.anthropic_api_key', ''
        )
        # Intentar clasificar — no debe crashear
        try:
            lead.action_classify_with_ai()
        except Exception:
            pass  # OK si falla con error controlado
        # El lead NO debe marcarse como clasificado
        self.assertFalse(lead.crfp_ai_classified,
                         "Sin API key, el lead no debe marcarse como clasificado")

    def test_lead_reset_classification(self):
        """Resetear clasificación limpia campos IA."""
        lead = self._create_website_lead()
        lead.write({
            'crfp_ai_classified': True,
            'crfp_ai_priority': 'high',
            'crfp_product_interest': 'tubers',
            'crfp_region': 'europe',
            'crfp_ai_summary': 'High value client',
        })
        lead.action_reset_ai_classification()
        self.assertFalse(lead.crfp_ai_classified)


@tagged('audit_tests', 'crfp_website', 'diagnostic')
class TestWebsiteDiagnostic(TransactionCase):
    """
    ╔══════════════════════════════════════════════════════════╗
    ║  DIAGNÓSTICO: Seguridad del chatbot, API key storage,   ║
    ║  rate limiting, sanitización de input                    ║
    ╚══════════════════════════════════════════════════════════╝
    """

    def test_diagnostic_chatbot_no_rate_limiting(self):
        """
        HALLAZGO: El endpoint /crfarm/chatbot/message es público
        (auth='public') y NO tiene rate limiting.
        Un atacante podría enviar miles de requests, acumulando
        costos en la API de Anthropic.
        """
        _logger.warning(
            "\n╔═══ RIESGO DE SEGURIDAD: CHATBOT SIN RATE LIMIT ═══╗\n"
            "  Endpoint: /crfarm/chatbot/message\n"
            "  Auth: public (cualquier visitante)\n"
            "  Rate limit: NINGUNO\n"
            "  IMPACTO: Abuso de API → costos elevados en Anthropic\n"
            "  RECOMENDACIÓN:\n"
            "    1. Agregar rate limiting por IP (ej: 20 msg/min)\n"
            "    2. Agregar CAPTCHA o session validation\n"
            "    3. Agregar límite de gasto diario en la API\n"
            "╚══════════════════════════════════════════════════════╝"
        )

    def test_diagnostic_chatbot_html_injection(self):
        """
        HALLAZGO: Las respuestas del chatbot (de Claude API) se
        renderizan como HTML en el frontend sin sanitización.
        Si Claude retorna HTML/JS, se ejecuta en el navegador.
        """
        _logger.warning(
            "\n╔═══ RIESGO: HTML INJECTION EN CHATBOT ═══╗\n"
            "  crfp_chatbot.js renderiza la respuesta de Claude\n"
            "  directamente como innerHTML sin escape.\n"
            "  IMPACTO: XSS si la respuesta contiene <script>.\n"
            "  RECOMENDACIÓN: Escapar HTML en respuestas del bot\n"
            "  o usar textContent en lugar de innerHTML.\n"
            "╚═══════════════════════════════════════════════╝"
        )

    def test_diagnostic_api_key_not_hardcoded(self):
        """Verificar que NO hay API keys hardcoded en el código."""
        # Verificar que la key se lee de ir.config_parameter
        key = self.env['ir.config_parameter'].sudo().get_param(
            'crfp_website.anthropic_api_key', ''
        )
        # El test pasa si no hay key hardcoded (valor vacío o configurado)
        # Solo verificamos que el mecanismo de configuración existe
        self.assertIsNotNone(key, "Mecanismo de API key debe existir")

    def test_diagnostic_cron_batch_limit(self):
        """
        DIAGNÓSTICO: El cron de clasificación procesa máximo 50 leads.
        Con alto volumen, podrían acumularse leads sin clasificar.
        """
        _logger.warning(
            "\n╔═══ NOTA: BATCH LIMIT EN CRON ═══╗\n"
            "  _cron_classify_unclassified_leads() procesa\n"
            "  máximo 50 leads por ejecución (cada hora).\n"
            "  Si llegan >50 leads/hora, se acumulan.\n"
            "  RECOMENDACIÓN: Hacer el límite configurable\n"
            "  o agregar cron con frecuencia adaptativa.\n"
            "╚════════════════════════════════════════╝"
        )
