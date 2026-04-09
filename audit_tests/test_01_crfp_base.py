# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════
  TEST 01 — crfp_base: Datos Maestros y Configuración
  Diagnóstico: campos duplicados, settings vs fixed costs,
  stub de res.users, acceso de seguridad
═══════════════════════════════════════════════════════════════
"""
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import UserError, ValidationError


@tagged('audit_tests', 'crfp_base')
class TestCrfpBaseModels(TransactionCase):
    """Verifica que todos los modelos base se crean correctamente."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    # ─── PUERTOS ─────────────────────────────────────────────
    def test_port_create_and_display_name(self):
        """Puerto se crea correctamente y display_name usa formato CODE - NAME (COUNTRY)."""
        port = self.env['crfp.port'].create({
            'code': 'TST',
            'name': 'Test Port',
            'country': 'Test Country',
            'region': 'europe',
        })
        self.assertTrue(port.id)
        self.assertIn('TST', port.display_name)
        self.assertIn('Test Port', port.display_name)

    def test_port_code_unique_constraint(self):
        """SQL constraint: código de puerto debe ser único."""
        self.env['crfp.port'].create({
            'code': 'UNQ', 'name': 'Port 1', 'country': 'CR', 'region': 'central_america',
        })
        with self.assertRaises(Exception):
            self.env['crfp.port'].create({
                'code': 'UNQ', 'name': 'Port 2', 'country': 'CR', 'region': 'central_america',
            })

    # ─── CONTENEDORES ────────────────────────────────────────
    def test_container_type_create(self):
        """Tipo de contenedor se crea con código único."""
        ct = self.env['crfp.container.type'].create({
            'code': 'test40hrf', 'name': 'Test 40ft Reefer', 'capacity_boxes': 1386, 'is_reefer': True,
        })
        self.assertTrue(ct.is_reefer)
        self.assertEqual(ct.capacity_boxes, 1386)

    # ─── PRODUCTOS ───────────────────────────────────────────
    def test_product_compute_total_cost_per_kg(self):
        """total_cost_per_kg = labor + materials + indirect."""
        product = self.env['crfp.product'].create({
            'name': 'AUDIT TEST PRODUCT',
            'category': 'tubers',
            'labor_per_kg': 0.10,
            'materials_per_kg': 0.05,
            'indirect_per_kg': 0.03,
        })
        self.assertAlmostEqual(product.total_cost_per_kg, 0.18, places=4)

    def test_product_calc_types_exist(self):
        """Todos los calc_type válidos son aceptados."""
        for calc_type in ['standard', 'flat_no_box', 'flat_plus_box', 'kg_no_box']:
            product = self.env['crfp.product'].create({
                'name': f'AUDIT {calc_type}',
                'category': 'tubers',
                'calc_type': calc_type,
            })
            self.assertEqual(product.calc_type, calc_type)

    # ─── PALLET CONFIG ───────────────────────────────────────
    def test_pallet_config_display_name(self):
        """Display name incluye keyword, peso y cajas."""
        pallet = self.env['crfp.pallet.config'].create({
            'product_keyword': 'YUCA VALENCIANA',
            'weight_kg': 18.0,
            'boxes_per_pallet': 66,
        })
        self.assertIn('YUCA VALENCIANA', pallet.display_name)

    # ─── INCOTERM MATRIX ─────────────────────────────────────
    def test_incoterm_matrix_all_codes(self):
        """Todos los incoterms del campo Selection son válidos."""
        valid_codes = ['EXW', 'FCA', 'FOB', 'CFR', 'CIF', 'CPT', 'CIP', 'DAP', 'DDP']
        for code in valid_codes:
            # Verificar que no falla al crear (solo si no existe ya)
            existing = self.env['crfp.incoterm.matrix'].search([('code', '=', code)])
            if not existing:
                matrix = self.env['crfp.incoterm.matrix'].create({'code': code})
                self.assertEqual(matrix.code, code)


@tagged('audit_tests', 'crfp_base', 'diagnostic')
class TestCrfpBaseSettingsVsFixedCosts(TransactionCase):
    """
    ╔══════════════════════════════════════════════════════════╗
    ║  DIAGNÓSTICO: Duplicación entre crfp.settings y         ║
    ║  crfp.fixed.cost — ¿cuál se usa realmente?              ║
    ╚══════════════════════════════════════════════════════════╝
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def test_settings_singleton_per_company(self):
        """Solo un registro de settings por empresa."""
        settings = self.env['crfp.settings'].get_settings()
        self.assertTrue(settings.id)
        # Intentar crear otro debe fallar
        with self.assertRaises(UserError):
            self.env['crfp.settings'].create({'name': 'Duplicate'})

    def test_fixed_cost_singleton_per_company(self):
        """Solo un registro de fixed cost por empresa."""
        fc = self.env['crfp.fixed.cost'].get_fixed_costs()
        self.assertTrue(fc.id)

    def test_diagnostic_settings_and_fixed_cost_overlap(self):
        """
        DIAGNÓSTICO: Detecta campos semánticamente duplicados.
        Ambos modelos almacenan costos similares — esto genera
        riesgo de inconsistencia si se actualiza uno y no el otro.
        """
        settings = self.env['crfp.settings'].get_settings()
        fc = self.env['crfp.fixed.cost'].get_fixed_costs()

        # Mapeo de campos equivalentes entre ambos modelos
        overlap_map = {
            'fc_transport_default': 'transport',
            'fc_thc_origin_default': 'thc_origin',
            'fc_fumigation_default': 'fumigation',
            'fc_broker_default': 'broker',
            'fc_thc_dest_default': 'thc_dest',
            'fc_fumig_dest_default': 'fumig_dest',
            'fc_inland_dest_default': 'inland_dest',
            'fc_insurance_pct_default': 'insurance_pct',
            'fc_duties_pct_default': 'duties_pct',
        }

        mismatches = []
        for s_field, fc_field in overlap_map.items():
            s_val = getattr(settings, s_field, None)
            fc_val = getattr(fc, fc_field, None)
            if s_val is not None and fc_val is not None and abs(s_val - fc_val) > 0.01:
                mismatches.append(
                    f"  MISMATCH: settings.{s_field}={s_val} vs fixed_cost.{fc_field}={fc_val}"
                )

        # Este test DOCUMENTA el problema — no falla, pero reporta
        if mismatches:
            import logging
            _logger = logging.getLogger(__name__)
            _logger.warning(
                "\n╔═══ DIAGNÓSTICO: VALORES INCONSISTENTES ═══╗\n"
                "%s\n"
                "╚═══ RECOMENDACIÓN: Unificar en un solo modelo ═══╝",
                "\n".join(mismatches)
            )

        # Verificar que AMBOS modelos tienen defaults razonables (no cero total)
        self.assertGreater(settings.fc_transport_default, 0,
                           "Settings: transporte default no debería ser 0")
        self.assertGreater(fc.transport, 0,
                           "Fixed Cost: transporte no debería ser 0")

    def test_diagnostic_which_model_quotation_uses(self):
        """
        DIAGNÓSTICO: ¿Cuál modelo usa crfp.quotation para defaults?
        Respuesta esperada: crfp.settings (NO crfp.fixed.cost).
        """
        settings = self.env['crfp.settings'].get_settings()

        # Simular lo que hace crfp.quotation.default_get()
        # La cotización debería cargar de settings, no de fixed_cost
        Quotation = self.env.get('crfp.quotation')
        if Quotation is not None:
            # Verificar que el default_get realmente lee de settings
            defaults = Quotation.default_get(['exchange_rate', 'fc_transport'])
            if defaults.get('exchange_rate'):
                self.assertAlmostEqual(
                    defaults['exchange_rate'], settings.exchange_rate, places=1,
                    msg="Quotation debería cargar tipo de cambio de crfp.settings"
                )

    def test_diagnostic_bccr_xml_parser(self):
        """DIAGNÓSTICO: El parser de XML del BCCR maneja datos malformados."""
        Settings = self.env['crfp.settings']
        # XML válido
        valid_xml = '<Datos_Output><INGC011_CAT_INDICADORECONOMIC><NUM_VALOR>503,25</NUM_VALOR></INGC011_CAT_INDICADORECONOMIC></Datos_Output>'
        result = Settings._parse_bccr_response(valid_xml)
        self.assertIsNotNone(result, "Parser debe extraer rate de XML válido")
        self.assertAlmostEqual(result, 503.25, places=2)

        # XML malformado
        result_bad = Settings._parse_bccr_response('<invalid>')
        self.assertIsNone(result_bad, "Parser debe retornar None con XML malformado")

        # XML vacío
        result_empty = Settings._parse_bccr_response('')
        self.assertIsNone(result_empty, "Parser debe retornar None con string vacío")


@tagged('audit_tests', 'crfp_base', 'diagnostic')
class TestCrfpBaseStubAndOrphanedCode(TransactionCase):
    """
    ╔══════════════════════════════════════════════════════════╗
    ║  DIAGNÓSTICO: Archivo stub crfp_res_users.py y vista    ║
    ║  que referencia campo inexistente crfp_role              ║
    ╚══════════════════════════════════════════════════════════╝
    """

    def test_diagnostic_res_users_no_crfp_role_field(self):
        """
        HALLAZGO: crfp_res_users_views.xml referencia 'crfp_role'
        en res.users, pero el campo NO existe (modelo es un stub).
        Esto puede generar un error al renderizar la vista.
        """
        User = self.env['res.users']
        has_crfp_role = 'crfp_role' in User._fields
        if not has_crfp_role:
            import logging
            logging.getLogger(__name__).warning(
                "\n╔═══ HALLAZGO: CAMPO HUÉRFANO ═══╗\n"
                "  crfp_role NO existe en res.users\n"
                "  pero crfp_res_users_views.xml lo referencia.\n"
                "  ACCIÓN: Eliminar la vista o definir el campo.\n"
                "╚════════════════════════════════════╝"
            )
        # No hacemos fail, pero documentamos

    def test_diagnostic_carrier_model_used(self):
        """
        DIAGNÓSTICO: ¿El modelo crfp.carrier se usa en algún módulo?
        Solo freight_quote tiene carrier_id (DEPRECATED).
        """
        Carrier = self.env.get('crfp.carrier')
        if Carrier is not None:
            # Verificar si algún freight quote lo referencia
            FreightQuote = self.env.get('crfp.freight.quote')
            if FreightQuote is not None:
                has_carrier_id = 'carrier_id' in FreightQuote._fields
                has_carrier_partner_id = 'carrier_partner_id' in FreightQuote._fields
                if has_carrier_id and has_carrier_partner_id:
                    import logging
                    logging.getLogger(__name__).warning(
                        "\n╔═══ HALLAZGO: CAMPO DEPRECATED ═══╗\n"
                        "  crfp.freight.quote tiene AMBOS:\n"
                        "    - carrier_id (DEPRECATED → crfp.carrier)\n"
                        "    - carrier_partner_id (ACTIVO → res.partner)\n"
                        "  ACCIÓN: Eliminar carrier_id y crfp.carrier si no se usa.\n"
                        "╚═══════════════════════════════════════╝"
                    )
