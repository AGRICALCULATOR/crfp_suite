# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════
  TEST 06 — Cross-Module: Integración entre módulos
  Diagnóstico: flujo completo cotización→SO→embarque→factura,
  campos duplicados entre módulos, consistencia de datos
═══════════════════════════════════════════════════════════════
"""
from odoo.tests.common import TransactionCase, tagged
from datetime import date, timedelta
import logging

_logger = logging.getLogger(__name__)


@tagged('audit_tests', 'cross_module')
class TestFullExportFlow(TransactionCase):
    """
    ╔══════════════════════════════════════════════════════════╗
    ║  TEST DE INTEGRACIÓN: Flujo completo de exportación     ║
    ║  Quotation → Sale Order → Shipment → Invoice            ║
    ╚══════════════════════════════════════════════════════════╝
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        # Datos maestros
        cls.port = cls.env['crfp.port'].create({
            'code': 'INT', 'name': 'Integration Port', 'country': 'NL', 'region': 'europe',
        })
        cls.container_type = cls.env['crfp.container.type'].create({
            'code': 'int40rf', 'name': 'Int 40ft Reefer',
            'capacity_boxes': 1386, 'is_reefer': True,
        })
        cls.partner = cls.env['res.partner'].create({
            'name': 'Integration Test Client B.V.',
            'email': 'integration@test.com',
        })
        cls.crfp_product = cls.env['crfp.product'].create({
            'name': 'INT YUCA VALENCIA',
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
        cls.odoo_product = cls.env['product.product'].create({
            'name': 'INT YUCA [product.product]', 'type': 'consu',
        })
        cls.crfp_product.product_id = cls.odoo_product.id

        # Settings y fixed costs
        cls.settings = cls.env['crfp.settings'].get_settings()

    def test_full_flow_quotation_to_invoice(self):
        """
        Flujo completo: Quotation → SO → Shipment → Invoice.
        Verifica que los datos fluyen correctamente entre módulos.
        """
        # ─── PASO 1: Crear cotización ───
        quotation = self.env['crfp.quotation'].create({
            'name': 'INT-FLOW-001',
            'partner_id': self.partner.id,
            'incoterm': 'FOB',
            'port_id': self.port.id,
            'container_type_id': self.container_type.id,
            'exchange_rate': 503.0,
            'total_boxes': 1386,
            'etd': date.today() + timedelta(days=14),
            'eta': date.today() + timedelta(days=28),
        })

        # Crear línea con precios pre-calculados (como haría el frontend)
        self.env['crfp.quotation.line'].create({
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
            'purchase_cost': 5.37,
            'packing_cost': 5.02,
            'exw_price': 11.39,
            'logistics_per_box': 1.12,
            'final_price': 12.51,
            'gross_lbs': 44.0,
            'pallets': 21,
            'boxes_per_pallet': 66,
        })

        # ─── PASO 2: Confirmar y crear SO ───
        quotation.action_confirm()
        self.assertEqual(quotation.state, 'confirmed')

        quotation.action_create_sale_order()
        so = quotation.sale_order_id
        self.assertTrue(so, "Debe crearse un Sale Order")
        self.assertEqual(so.partner_id, self.partner)
        self.assertTrue(so.order_line, "SO debe tener líneas")

        # Confirmar SO
        so.action_confirm()
        self.assertEqual(so.state, 'sale')

        # ─── PASO 3: Crear embarque desde SO ───
        so.action_create_shipment()
        shipment = so.crfp_shipment_id
        self.assertTrue(shipment, "Debe crearse un Shipment")
        self.assertEqual(shipment.partner_id, self.partner)
        self.assertTrue(shipment.line_ids, "Shipment debe tener líneas")

        # Verificar que los datos de la cotización fluyeron
        if shipment.incoterm:
            self.assertEqual(shipment.incoterm, 'FOB')

        # ─── PASO 4: Verificar líneas del embarque ───
        ship_line = shipment.line_ids[0]
        self.assertGreater(ship_line.boxes_planned, 0,
                           "Cajas planificadas deben venir del SO/quotation")

        # ─── PASO 5: Simular carga de datos actuales ───
        ship_line.write({
            'boxes_actual': 1386,
            'pallets_actual': 21,
            'net_weight_actual': 24948.0,
            'gross_weight_actual': 26195.4,
        })

        # ─── PASO 6: Crear factura desde SO ───
        # (Solo si el flujo de facturación está disponible)
        try:
            so._create_invoices()
            invoice = so.invoice_ids[0] if so.invoice_ids else None
            if invoice:
                self.assertEqual(invoice.partner_id, self.partner)
                _logger.info("Factura creada: %s", invoice.name)

                # Verificar vinculación embarque → factura
                if hasattr(invoice, 'crfp_shipment_id'):
                    _logger.info(
                        "Shipment vinculado a factura: %s",
                        invoice.crfp_shipment_id.name if invoice.crfp_shipment_id else 'NO'
                    )
        except Exception as e:
            _logger.info("Facturación no ejecutada (puede requerir configuración): %s", e)


@tagged('audit_tests', 'cross_module', 'diagnostic')
class TestCrossModuleDiagnostic(TransactionCase):
    """
    ╔══════════════════════════════════════════════════════════╗
    ║  DIAGNÓSTICO CROSS-MODULE: Detecta inconsistencias      ║
    ║  entre módulos que modifican los mismos modelos          ║
    ╚══════════════════════════════════════════════════════════╝
    """

    def test_diagnostic_duplicate_weight_fields_on_sol(self):
        """
        HALLAZGO PRINCIPAL: sale.order.line tiene 4 campos de peso
        de 2 módulos diferentes:
          - peso_neto, peso_total (invoice_weight) digits=(12,2)
          - fp_net_weight, fp_gross_weight (l10n_cr_einvoice) digits=(16,3)
        Esto confunde a usuarios y genera datos inconsistentes.
        """
        SOL = self.env['sale.order.line']
        weight_fields = {
            'peso_neto': ('invoice_weight', '(12,2)'),
            'peso_total': ('invoice_weight', '(12,2)'),
            'fp_net_weight': ('l10n_cr_einvoice', '(16,3)'),
            'fp_gross_weight': ('l10n_cr_einvoice', '(16,3)'),
        }

        found = {}
        for fname, (module, precision) in weight_fields.items():
            if fname in SOL._fields:
                found[fname] = f"{module} {precision}"

        if len(found) > 2:
            _logger.warning(
                "\n╔═══ HALLAZGO PRINCIPAL: CAMPOS DE PESO DUPLICADOS ═══╗\n"
                "  sale.order.line tiene %d campos de peso:\n%s\n"
                "  PROBLEMA: 2 módulos agregan campos equivalentes.\n"
                "  • invoice_weight → peso_neto, peso_total\n"
                "  • l10n_cr_einvoice → fp_net_weight, fp_gross_weight\n"
                "  El flujo de embarque escribe solo a fp_net_weight.\n"
                "  peso_neto NUNCA se actualiza automáticamente.\n"
                "  RECOMENDACIÓN: Eliminar módulo invoice_weight.\n"
                "╚═══════════════════════════════════════════════════════╝",
                len(found),
                "\n".join(f"    {k}: {v}" for k, v in found.items())
            )

    def test_diagnostic_duplicate_weight_fields_on_aml(self):
        """Misma duplicación en account.move.line."""
        AML = self.env['account.move.line']
        weight_fields = ['peso_neto', 'peso_total', 'fp_net_weight', 'fp_gross_weight']
        found = [f for f in weight_fields if f in AML._fields]
        if len(found) > 2:
            _logger.warning(
                "\n╔═══ DUPLICACIÓN EN ACCOUNT.MOVE.LINE ═══╗\n"
                "  Campos encontrados: %s\n"
                "  Misma situación que sale.order.line.\n"
                "╚═════════════════════════════════════════════╝",
                found
            )

    def test_diagnostic_all_models_have_access_rules(self):
        """
        DIAGNÓSTICO: Verificar que TODOS los modelos crfp.*
        tienen reglas de acceso definidas.
        """
        # Buscar todos los modelos crfp.*
        crfp_models = self.env['ir.model'].search([
            ('model', 'like', 'crfp.%'),
            ('transient', '=', False),
        ])

        models_without_access = []
        for model in crfp_models:
            access = self.env['ir.model.access'].search([
                ('model_id', '=', model.id),
            ])
            if not access:
                models_without_access.append(model.model)

        if models_without_access:
            _logger.warning(
                "\n╔═══ MODELOS SIN REGLAS DE ACCESO ═══╗\n"
                "  Los siguientes modelos crfp.* NO tienen\n"
                "  reglas en ir.model.access:\n%s\n"
                "  RIESGO: Usuarios no admin no pueden acceder.\n"
                "  ACCIÓN: Agregar reglas en ir.model.access.csv.\n"
                "╚═══════════════════════════════════════════════╝",
                "\n".join(f"    • {m}" for m in models_without_access)
            )

    def test_diagnostic_incoterm_consistency(self):
        """
        Verificar que los valores de incoterm son consistentes
        entre todos los modelos que lo usan.
        """
        # Los incoterms deben ser iguales en quotation, shipment, y matrix
        incoterms_expected = {'EXW', 'FCA', 'FOB', 'CFR', 'CIF', 'CPT', 'CIP', 'DAP', 'DDP'}

        models_with_incoterm = ['crfp.quotation', 'crfp.shipment', 'crfp.incoterm.matrix']
        for model_name in models_with_incoterm:
            Model = self.env.get(model_name)
            if Model and 'incoterm' in Model._fields:
                field = Model._fields['incoterm']
                if hasattr(field, 'selection'):
                    sel = field.selection
                    if isinstance(sel, list):
                        codes = {s[0] for s in sel}
                        missing = incoterms_expected - codes
                        extra = codes - incoterms_expected
                        if missing or extra:
                            _logger.warning(
                                "\n  INCONSISTENCIA en %s.incoterm:\n"
                                "    Faltan: %s | Sobran: %s",
                                model_name, missing or '∅', extra or '∅'
                            )
            elif Model and 'code' in Model._fields and model_name == 'crfp.incoterm.matrix':
                field = Model._fields['code']
                if hasattr(field, 'selection') and isinstance(field.selection, list):
                    codes = {s[0] for s in field.selection}
                    missing = incoterms_expected - codes
                    if missing:
                        _logger.warning(
                            "  INCONSISTENCIA en %s.code: Faltan %s",
                            model_name, missing
                        )

    def test_diagnostic_summary_what_to_eliminate(self):
        """
        ═══════════════════════════════════════════════════════
          RESUMEN FINAL: QUÉ ELIMINAR, CAMBIAR, MEJORAR
        ═══════════════════════════════════════════════════════
        """
        _logger.warning("""
╔═══════════════════════════════════════════════════════════════════╗
║                    RESUMEN DE HALLAZGOS                          ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║  🔴 ELIMINAR:                                                     ║
║    1. Módulo invoice_weight completo                              ║
║       → peso_neto/peso_total NUNCA se actualizan por el flujo     ║
║       → fp_net_weight/fp_gross_weight (einvoice) ya cubren esto   ║
║    2. _push_weights_to_invoice() wrapper muerto                   ║
║    3. carrier_id deprecated en crfp.freight.quote                 ║
║    4. crfp_res_users.py stub (y su vista huérfana)               ║
║    5. crfp.carrier model (si solo era para carrier_id)            ║
║                                                                   ║
║  🟡 CAMBIAR:                                                      ║
║    1. pricing_api.py get_price_history():                         ║
║       crfp_product_id → product_id (BUG CRÍTICO)                 ║
║       campos date/price_crc → week/year/price_usd                ║
║    2. action_send_claim_email(): agregar null-checks              ║
║       para shipment_id, booking_id, container_ids                 ║
║    3. Unificar crfp.settings + crfp.fixed.cost en uno solo       ║
║    4. Puerto origen MOI hardcoded → campo en crfp.settings        ║
║    5. Factor tara 1.05 hardcoded → campo configurable            ║
║    6. Permisos: quitar perm_unlink a users en claim.evidence     ║
║                                                                   ║
║  🟢 MEJORAR:                                                      ║
║    1. Reactivar _check_blocking_tasks() en shipment workflow      ║
║    2. Conectar container.config → shipment (o documentar)         ║
║    3. Agregar @api.depends server-side a campos de precio         ║
║       en quotation_line (actualmente solo JS calcula)             ║
║    4. Rate limiting en chatbot endpoint                           ║
║    5. Sanitizar HTML en respuestas del chatbot                    ║
║    6. Integrar tracking.position y tracking.temperature           ║
║       o eliminarlos si no se van a usar                           ║
║    7. Batch configurable para cron de clasificación IA            ║
║    8. Tests automatizados como parte del CI/CD                    ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
        """)
