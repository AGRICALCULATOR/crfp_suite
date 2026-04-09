# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════
  TEST 02 — crfp_pricing: Cotizaciones, Precios, Field Buyer
  Diagnóstico: campos no-computed, API field mismatch,
  price history, flujo completo cotización→SO
═══════════════════════════════════════════════════════════════
"""
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import UserError
from unittest.mock import patch
import logging

_logger = logging.getLogger(__name__)


@tagged('audit_tests', 'crfp_pricing')
class TestCrfpQuotationFlow(TransactionCase):
    """Flujo funcional: Cotización → Sale Order."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        # Datos maestros necesarios
        cls.port = cls.env['crfp.port'].create({
            'code': 'AUD', 'name': 'Audit Port', 'country': 'NL', 'region': 'europe',
        })
        cls.container_type = cls.env['crfp.container.type'].create({
            'code': 'aud40hrf', 'name': 'Audit 40ft Reefer',
            'capacity_boxes': 1386, 'is_reefer': True,
        })
        cls.partner = cls.env['res.partner'].create({
            'name': 'Audit Client B.V.', 'email': 'audit@test.com',
        })
        cls.crfp_product = cls.env['crfp.product'].create({
            'name': 'AUDIT YUCA',
            'category': 'tubers',
            'net_kg': 18.0,
            'raw_price_crc': 150.0,
            'default_box_cost': 2.50,
            'labor_per_kg': 0.08,
            'materials_per_kg': 0.04,
            'indirect_per_kg': 0.02,
            'default_profit': 1.00,
            'calc_type': 'standard',
            'purchase_formula': 'standard',
            'gross_weight_type': 'standard',
        })
        # Asegurar producto Odoo enlazado
        cls.odoo_product = cls.env['product.product'].create({
            'name': 'AUDIT YUCA [product.product]',
            'type': 'consu',
        })
        cls.crfp_product.product_id = cls.odoo_product.id

        # Asegurar settings
        cls.settings = cls.env['crfp.settings'].get_settings()

    def _create_quotation_with_line(self):
        """Helper: crea una cotización con una línea completa."""
        quotation = self.env['crfp.quotation'].create({
            'name': 'AUD-TEST-001',
            'partner_id': self.partner.id,
            'incoterm': 'FOB',
            'port_id': self.port.id,
            'container_type_id': self.container_type.id,
            'exchange_rate': 503.0,
            'total_boxes': 1386,
        })
        line = self.env['crfp.quotation.line'].create({
            'quotation_id': quotation.id,
            'crfp_product_id': self.crfp_product.id,
            'product_id': self.odoo_product.id,
            'raw_price_crc': 150.0,
            'net_kg': 18.0,
            'box_cost': 2.50,
            'labor_per_kg': 0.08,
            'materials_per_kg': 0.04,
            'indirect_per_kg': 0.02,
            'profit': 1.00,
            'purchase_cost': 5.37,      # pre-calculado por frontend
            'packing_cost': 5.02,       # pre-calculado por frontend
            'exw_price': 11.39,         # pre-calculado por frontend
            'logistics_per_box': 1.12,  # pre-calculado por frontend
            'final_price': 12.51,       # pre-calculado por frontend
            'gross_lbs': 44.0,
            'pallets': 21,
            'boxes_per_pallet': 66,
        })
        return quotation, line

    def test_quotation_create_with_defaults(self):
        """Cotización se crea y carga defaults de crfp.settings."""
        quotation = self.env['crfp.quotation'].create({
            'name': 'AUD-DEFAULT-001',
            'partner_id': self.partner.id,
            'incoterm': 'FOB',
        })
        # Debe tener tipo de cambio del settings
        self.assertGreater(quotation.exchange_rate, 0,
                           "Exchange rate debe cargarse de crfp.settings")

    def test_quotation_line_totals_computed(self):
        """total_boxes = pallets * boxes_per_pallet, line_total = total_boxes * final_price."""
        quotation, line = self._create_quotation_with_line()
        self.assertEqual(line.total_boxes, 21 * 66)  # 1386
        self.assertAlmostEqual(line.line_total, 1386 * 12.51, places=1)

    def test_quotation_line_gross_kg_from_lbs(self):
        """gross_kg se calcula automáticamente de gross_lbs."""
        _, line = self._create_quotation_with_line()
        expected_kg = 44.0 / 2.20462
        self.assertAlmostEqual(line.gross_kg, expected_kg, places=0)

    def test_quotation_create_sale_order(self):
        """action_create_sale_order genera un sale.order vinculado."""
        quotation, _ = self._create_quotation_with_line()
        quotation.action_confirm()
        result = quotation.action_create_sale_order()
        self.assertTrue(quotation.sale_order_id,
                        "Debe crearse un SO vinculado a la cotización")
        so = quotation.sale_order_id
        self.assertEqual(so.partner_id, self.partner)
        self.assertTrue(so.order_line, "SO debe tener líneas de producto")

    def test_quotation_totals_aggregation(self):
        """Totales de cotización suman correctamente."""
        quotation, line = self._create_quotation_with_line()
        self.assertEqual(quotation.line_count, 1)
        self.assertGreater(quotation.total_amount, 0)
        self.assertGreater(quotation.total_order_amount, 0)


@tagged('audit_tests', 'crfp_pricing', 'diagnostic')
class TestCrfpPricingDiagnostic(TransactionCase):
    """
    ╔══════════════════════════════════════════════════════════╗
    ║  DIAGNÓSTICO: Campos de quotation_line NO son computed  ║
    ║  → se calculan por frontend JS, no por Python           ║
    ╚══════════════════════════════════════════════════════════╝
    """

    def test_diagnostic_non_computed_price_fields(self):
        """
        HALLAZGO: purchase_cost, packing_cost, exw_price,
        logistics_per_box, final_price NO son campos computed.
        Se calculan en JavaScript (calculator_service.js) y se
        guardan vía API. Riesgo: si alguien crea líneas sin el
        frontend, los precios quedan en 0.
        """
        Line = self.env['crfp.quotation.line']
        non_computed_fields = [
            'purchase_cost', 'packing_cost', 'exw_price',
            'logistics_per_box', 'final_price'
        ]
        findings = []
        for fname in non_computed_fields:
            field = Line._fields.get(fname)
            if field and not field.compute:
                findings.append(f"  {fname}: Float NO COMPUTED (valor escribible)")

        if findings:
            _logger.warning(
                "\n╔═══ HALLAZGO: CAMPOS DE PRECIO NO-COMPUTED ═══╗\n"
                "%s\n"
                "  RIESGO: Crear líneas por Python (ej: importación, API)\n"
                "  resulta en precios = 0.00. Solo el frontend JS calcula.\n"
                "  RECOMENDACIÓN: Agregar @api.depends con lógica de\n"
                "  cálculo como fallback server-side.\n"
                "╚════════════════════════════════════════════════════╝",
                "\n".join(findings)
            )


@tagged('audit_tests', 'crfp_pricing', 'diagnostic')
class TestCrfpPricingApiFieldBug(TransactionCase):
    """
    ╔══════════════════════════════════════════════════════════╗
    ║  DIAGNÓSTICO CRÍTICO: BUG en pricing_api.py             ║
    ║  get_price_history() usa nombres de campo incorrectos   ║
    ╚══════════════════════════════════════════════════════════╝
    """

    def test_diagnostic_price_history_field_names(self):
        """
        BUG CONFIRMADO: pricing_api.py línea 331 busca 'crfp_product_id'
        pero crfp.price.history define 'product_id'.
        También pide campos inexistentes: 'date', 'price_crc', 'exchange_rate'.
        Los campos reales son: 'week', 'year', 'price_usd', 'price_local'.
        """
        History = self.env['crfp.price.history']

        # Verificar campos que EXISTEN en el modelo
        actual_fields = set(History._fields.keys())

        # Campos que el API endpoint ESPERA (incorrectamente)
        api_expects = {'crfp_product_id', 'date', 'price_crc', 'exchange_rate', 'price_usd'}
        # Campos que REALMENTE existen
        api_correct = {'product_id', 'week', 'year', 'price_usd', 'price_local', 'currency_id', 'source', 'version', 'client_id'}

        missing_in_model = api_expects - actual_fields
        if missing_in_model:
            _logger.warning(
                "\n╔═══ BUG CRÍTICO: pricing_api.py get_price_history() ═══╗\n"
                "  Campos que el API espera pero NO EXISTEN:\n"
                "    %s\n"
                "  Campos reales del modelo crfp.price.history:\n"
                "    %s\n"
                "  IMPACTO: El endpoint /crfp/api/price-history crashea\n"
                "  con KeyError al filtrar por producto.\n"
                "  CORRECCIÓN: Usar 'product_id' en lugar de 'crfp_product_id',\n"
                "  y los campos correctos: week, year, price_usd, price_local.\n"
                "╚═══════════════════════════════════════════════════════════╝",
                missing_in_model,
                api_correct & actual_fields
            )

        self.assertIn('product_id', actual_fields,
                       "El campo correcto es 'product_id', no 'crfp_product_id'")
        self.assertNotIn('crfp_product_id', actual_fields,
                         "BUG: 'crfp_product_id' no existe en crfp.price.history")
        self.assertNotIn('date', actual_fields,
                         "BUG: 'date' no existe — usar 'week' y 'year'")


@tagged('audit_tests', 'crfp_pricing', 'diagnostic')
class TestCrfpFreightQuoteDeprecated(TransactionCase):
    """Diagnóstico del campo deprecated carrier_id en freight quote."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.port = cls.env['crfp.port'].create({
            'code': 'FRT', 'name': 'Freight Port', 'country': 'NL', 'region': 'europe',
        })
        cls.partner = cls.env['res.partner'].create({'name': 'Test Carrier Line'})

    def test_freight_quote_create_with_partner(self):
        """Freight quote se crea con carrier_partner_id (campo activo)."""
        fq = self.env['crfp.freight.quote'].create({
            'carrier_partner_id': self.partner.id,
            'port_id': self.port.id,
            'all_in_freight': 2800.0,
        })
        self.assertEqual(fq.carrier_partner_id, self.partner)
        self.assertEqual(fq.state, 'draft')

    def test_freight_quote_expiration(self):
        """Quotes con valid_until pasado se marcan como expirados."""
        from datetime import date, timedelta
        fq = self.env['crfp.freight.quote'].create({
            'carrier_partner_id': self.partner.id,
            'port_id': self.port.id,
            'all_in_freight': 2800.0,
            'valid_until': date.today() - timedelta(days=1),
            'state': 'active',
        })
        self.assertTrue(fq.is_expired, "Quote con fecha pasada debe ser is_expired=True")

    def test_diagnostic_deprecated_carrier_id(self):
        """
        HALLAZGO: carrier_id (Many2one a crfp.carrier) está DEPRECATED.
        Solo se usa carrier_partner_id (Many2one a res.partner).
        """
        FQ = self.env['crfp.freight.quote']
        has_old = 'carrier_id' in FQ._fields
        has_new = 'carrier_partner_id' in FQ._fields
        if has_old and has_new:
            _logger.warning(
                "\n╔═══ HALLAZGO: CAMPO DEPRECATED EN USO ═══╗\n"
                "  crfp.freight.quote tiene ambos:\n"
                "    carrier_id → crfp.carrier (DEPRECATED)\n"
                "    carrier_partner_id → res.partner (ACTIVO)\n"
                "  ACCIÓN: Eliminar carrier_id del modelo.\n"
                "  Si crfp.carrier no se usa en otro lugar,\n"
                "  eliminar el modelo completo.\n"
                "╚═════════════════════════════════════════════╝"
            )


@tagged('audit_tests', 'crfp_pricing')
class TestCrfpPriceListFlow(TransactionCase):
    """Flujo: Cotización → Price List → Price History."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.crfp_product = cls.env['crfp.product'].create({
            'name': 'AUDIT PL PRODUCT', 'category': 'tubers',
        })

    def test_price_list_create_and_activate(self):
        """Price list se crea, confirma y activa correctamente."""
        pl = self.env['crfp.price.list'].create({
            'week_number': 15, 'year': 2026, 'version': 1,
        })
        self.assertEqual(pl.status, 'draft')
        self.assertIn('W15', pl.name)

        # Agregar línea
        self.env['crfp.price.list.line'].create({
            'price_list_id': pl.id,
            'product_id': self.crfp_product.id,
            'price': 12.50,
            'currency_id': self.env.ref('base.USD').id,
        })

        pl.action_confirm()
        self.assertEqual(pl.status, 'confirmed')

        pl.action_activate()
        self.assertEqual(pl.status, 'active')

        # Verificar que se crearon history records
        histories = self.env['crfp.price.history'].search([
            ('product_id', '=', self.crfp_product.id),
            ('week', '=', 15),
            ('year', '=', 2026),
        ])
        self.assertTrue(histories, "Activar price list debe crear price history records")

    def test_field_buyer_token_generation(self):
        """Field buyer genera token único de acceso."""
        buyer = self.env['crfp.field.buyer'].create({
            'name': 'Audit Buyer',
        })
        self.assertTrue(buyer.token, "Token debe auto-generarse")
        self.assertEqual(len(buyer.token), 16, "Token debe tener 16 caracteres")

        # Regenerar token
        old_token = buyer.token
        buyer.action_regenerate_token()
        self.assertNotEqual(buyer.token, old_token, "Token regenerado debe ser diferente")
