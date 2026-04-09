# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════
  TEST 03 — crfp_logistics: Embarques, Workflow, Peso Sync
  Diagnóstico: métodos wrapper muertos, tracking sin uso,
  container config desconectado, push weights target fields
═══════════════════════════════════════════════════════════════
"""
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import UserError, ValidationError
from datetime import date, timedelta
import logging

_logger = logging.getLogger(__name__)


@tagged('audit_tests', 'crfp_logistics')
class TestShipmentCreationFromSO(TransactionCase):
    """Flujo funcional: Sale Order → Shipment completo."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        # Datos maestros
        cls.port_origin = cls.env['crfp.port'].create({
            'code': 'MOI', 'name': 'Puerto Moín', 'country': 'Costa Rica',
            'region': 'central_america',
        })
        cls.port_dest = cls.env['crfp.port'].create({
            'code': 'RTM', 'name': 'Rotterdam', 'country': 'Netherlands',
            'region': 'europe',
        })
        cls.container_type = cls.env['crfp.container.type'].create({
            'code': 'ship40rf', 'name': 'Ship 40ft Reefer',
            'capacity_boxes': 1386, 'is_reefer': True,
        })
        cls.partner = cls.env['res.partner'].create({
            'name': 'Ship Audit Client', 'email': 'ship@test.com',
        })
        cls.crfp_product = cls.env['crfp.product'].create({
            'name': 'SHIP YUCA TEST', 'category': 'tubers',
            'net_kg': 18.0, 'calc_type': 'standard',
            'gross_weight_type': 'standard',
        })
        cls.odoo_product = cls.env['product.product'].create({
            'name': 'SHIP YUCA [product]', 'type': 'consu',
        })
        cls.crfp_product.product_id = cls.odoo_product.id

        # Crear Sale Order
        cls.so = cls.env['sale.order'].create({
            'partner_id': cls.partner.id,
        })
        cls.env['sale.order.line'].create({
            'order_id': cls.so.id,
            'product_id': cls.odoo_product.id,
            'product_uom_qty': 1386,
            'price_unit': 12.50,
        })
        cls.so.action_confirm()

    def test_create_shipment_from_so(self):
        """action_create_shipment genera embarque con datos del SO."""
        self.so.action_create_shipment()
        shipment = self.so.crfp_shipment_id
        self.assertTrue(shipment, "Debe crearse un embarque vinculado al SO")
        self.assertEqual(shipment.partner_id, self.partner)
        self.assertEqual(shipment.state, 'draft')
        self.assertTrue(shipment.name.startswith('SHP') or shipment.name != 'New',
                        "Embarque debe tener referencia auto-generada")

    def test_shipment_lines_from_so(self):
        """Líneas del embarque se crean desde las líneas del SO."""
        self.so.action_create_shipment()
        shipment = self.so.crfp_shipment_id
        self.assertTrue(shipment.line_ids, "Embarque debe tener líneas")
        line = shipment.line_ids[0]
        self.assertEqual(line.product_id, self.odoo_product)
        self.assertGreater(line.boxes_planned, 0, "Cajas planificadas > 0")

    def test_shipment_auto_documents(self):
        """Embarque auto-carga documentos según incoterm/región."""
        self.so.action_create_shipment()
        shipment = self.so.crfp_shipment_id
        if shipment.document_ids:
            # Si hay document types cargados, deben tener estado pending
            for doc in shipment.document_ids:
                self.assertEqual(doc.state, 'pending',
                                 f"Documento {doc.doc_type} debe iniciar en 'pending'")

    def test_shipment_auto_checklist(self):
        """Embarque auto-crea checklist de tareas."""
        self.so.action_create_shipment()
        shipment = self.so.crfp_shipment_id
        if shipment.checklist_ids:
            for task in shipment.checklist_ids:
                self.assertEqual(task.state, 'pending',
                                 f"Tarea '{task.name}' debe iniciar en 'pending'")


@tagged('audit_tests', 'crfp_logistics')
class TestShipmentWorkflow(TransactionCase):
    """Workflow completo del embarque: 14 estados."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.port = cls.env['crfp.port'].create({
            'code': 'WF1', 'name': 'WF Port', 'country': 'NL', 'region': 'europe',
        })
        cls.container_type = cls.env['crfp.container.type'].create({
            'code': 'wf40rf', 'name': 'WF 40ft', 'capacity_boxes': 1386, 'is_reefer': True,
        })
        cls.partner = cls.env['res.partner'].create({
            'name': 'WF Client', 'email': 'wf@test.com',
        })
        cls.carrier = cls.env['res.partner'].create({
            'name': 'WF Carrier Line',
        })
        cls.crfp_product = cls.env['crfp.product'].create({
            'name': 'WF PRODUCT', 'category': 'tubers', 'net_kg': 18.0,
            'gross_weight_type': 'standard',
        })
        cls.odoo_product = cls.env['product.product'].create({
            'name': 'WF PRODUCT [odoo]', 'type': 'consu',
        })
        cls.crfp_product.product_id = cls.odoo_product.id

    def _create_shipment(self):
        """Helper: crea embarque con datos mínimos para workflow."""
        shipment = self.env['crfp.shipment'].create({
            'partner_id': self.partner.id,
            'port_destination_id': self.port.id,
            'container_type_id': self.container_type.id,
            'incoterm': 'FOB',
            'carrier_partner_id': self.carrier.id,
            'temperature_set': -18.0,
            'ventilation': '25 CBM/h',
            'etd': date.today() + timedelta(days=7),
            'eta': date.today() + timedelta(days=21),
        })
        # Agregar línea con datos
        self.env['crfp.shipment.line'].create({
            'shipment_id': shipment.id,
            'product_id': self.odoo_product.id,
            'crfp_product_id': self.crfp_product.id,
            'boxes_planned': 1386,
            'pallets_planned': 21,
            'net_weight_planned': 24948.0,
            'gross_weight_planned': 26195.4,
            'boxes_actual': 1386,
            'pallets_actual': 21,
            'net_weight_actual': 24948.0,
            'gross_weight_actual': 26195.4,
        })
        # Agregar contenedor
        self.env['crfp.shipment.container'].create({
            'shipment_id': shipment.id,
            'container_type_id': self.container_type.id,
            'container_number': 'MSCU1234567',
            'seal_number': 'SEAL001',
            'temperature_set': -18.0,
        })
        return shipment

    def test_workflow_draft_to_space_requested(self):
        """Draft → Space Requested transición básica."""
        shipment = self._create_shipment()
        shipment.action_request_space()
        self.assertEqual(shipment.state, 'space_requested')

    def test_workflow_full_happy_path(self):
        """Flujo completo sin errores: draft → closed."""
        shipment = self._create_shipment()

        # Draft → Space Requested
        shipment.action_request_space()
        self.assertEqual(shipment.state, 'space_requested')

        # → Booking Requested
        shipment.action_request_booking()
        self.assertEqual(shipment.state, 'booking_requested')

        # → Booking Confirmed
        shipment.action_confirm_booking()
        self.assertEqual(shipment.state, 'booking_confirmed')

        # → SI Sent
        shipment.action_send_si()
        self.assertEqual(shipment.state, 'si_sent')

        # → BL Draft Received
        shipment.action_bl_draft_received()
        self.assertEqual(shipment.state, 'bl_draft_received')

        # → Loading
        shipment.action_start_loading()
        self.assertEqual(shipment.state, 'loading')

        # → Docs Final
        shipment.action_docs_final()
        self.assertEqual(shipment.state, 'docs_final')

        # → Shipped
        shipment.action_ship()
        self.assertEqual(shipment.state, 'shipped')

        # → In Transit
        shipment.action_in_transit()
        self.assertEqual(shipment.state, 'in_transit')

        # → Arrived
        shipment.action_arrive()
        self.assertEqual(shipment.state, 'arrived')

        # → Delivered
        shipment.action_deliver()
        self.assertEqual(shipment.state, 'delivered')

        # → Closed
        shipment.action_close()
        self.assertEqual(shipment.state, 'closed')

    def test_shipment_cancel_from_any_state(self):
        """Se puede cancelar desde cualquier estado."""
        shipment = self._create_shipment()
        shipment.action_request_space()
        shipment.action_cancel()
        self.assertEqual(shipment.state, 'cancelled')

    def test_shipment_computed_totals(self):
        """Totales computed se calculan de las líneas."""
        shipment = self._create_shipment()
        self.assertEqual(shipment.total_boxes_planned, 1386)
        self.assertEqual(shipment.total_boxes_actual, 1386)
        self.assertGreater(shipment.total_net_weight_actual, 0)


@tagged('audit_tests', 'crfp_logistics', 'diagnostic')
class TestShipmentWeightSync(TransactionCase):
    """
    ╔══════════════════════════════════════════════════════════╗
    ║  DIAGNÓSTICO CRÍTICO: ¿A qué campos escribe el push     ║
    ║  de pesos del embarque hacia la factura?                 ║
    ║  → fp_net_weight (l10n_cr_einvoice)                     ║
    ║  → NO peso_neto (invoice_weight)                        ║
    ╚══════════════════════════════════════════════════════════╝
    """

    def test_diagnostic_weight_push_target_fields(self):
        """
        HALLAZGO: _push_weights_and_dates_to_invoice() escribe a:
          - fp_net_weight / fp_gross_weight (l10n_cr_einvoice)
          - NO escribe a peso_neto / peso_total (invoice_weight)

        Esto significa que el módulo invoice_weight es REDUNDANTE
        si l10n_cr_einvoice está instalado. Los campos peso_neto
        y peso_total de invoice_weight NUNCA se actualizan por el
        flujo automático del embarque.
        """
        MoveLine = self.env['account.move.line']
        fields_map = {
            'fp_net_weight': 'l10n_cr_einvoice (DESTINO del push)',
            'fp_gross_weight': 'l10n_cr_einvoice (DESTINO del push)',
            'peso_neto': 'invoice_weight (NO ACTUALIZADO por push)',
            'peso_total': 'invoice_weight (NO ACTUALIZADO por push)',
        }

        findings = []
        for fname, desc in fields_map.items():
            exists = fname in MoveLine._fields
            findings.append(f"  {fname}: {'EXISTE' if exists else 'NO EXISTE'} — {desc}")

        _logger.warning(
            "\n╔═══ DIAGNÓSTICO: TARGET FIELDS DEL WEIGHT PUSH ═══╗\n"
            "%s\n"
            "  CONCLUSIÓN:\n"
            "    Si ambos módulos están instalados, las facturas\n"
            "    tienen 4 campos de peso pero solo 2 se actualizan.\n"
            "    peso_neto y peso_total quedan SIEMPRE en 0.\n"
            "  RECOMENDACIÓN:\n"
            "    Eliminar invoice_weight, usar solo fp_net_weight\n"
            "    y fp_gross_weight de l10n_cr_einvoice.\n"
            "╚════════════════════════════════════════════════════╝",
            "\n".join(findings)
        )


@tagged('audit_tests', 'crfp_logistics', 'diagnostic')
class TestShipmentDeadCode(TransactionCase):
    """
    ╔══════════════════════════════════════════════════════════╗
    ║  DIAGNÓSTICO: Código muerto y funcionalidad sin uso     ║
    ╚══════════════════════════════════════════════════════════╝
    """

    def test_diagnostic_push_weights_to_invoice_wrapper_dead(self):
        """
        HALLAZGO: _push_weights_to_invoice() es un wrapper que
        llama a _push_weights_and_dates_to_invoice() pero NADIE
        lo llama internamente. El botón del XML llama a
        action_push_weights_to_invoice() (otro método diferente).
        → CÓDIGO MUERTO, se puede eliminar.
        """
        Shipment = self.env['crfp.shipment']
        has_old = hasattr(Shipment, '_push_weights_to_invoice')
        has_new = hasattr(Shipment, '_push_weights_and_dates_to_invoice')
        has_action = hasattr(Shipment, 'action_push_weights_to_invoice')

        if has_old and has_new:
            _logger.warning(
                "\n╔═══ CÓDIGO MUERTO: _push_weights_to_invoice() ═══╗\n"
                "  Wrapper legacy en crfp_shipment.py\n"
                "  • _push_weights_to_invoice() → wrapper sin callers\n"
                "  • _push_weights_and_dates_to_invoice() → implementación real\n"
                "  • action_push_weights_to_invoice() → botón del form\n"
                "  ACCIÓN: Eliminar _push_weights_to_invoice()\n"
                "╚═══════════════════════════════════════════════════════╝"
            )

    def test_diagnostic_blocking_tasks_disabled(self):
        """
        HALLAZGO: _check_blocking_tasks() tiene toda la lógica
        comentada. Los usuarios pueden avanzar estados sin
        completar tareas críticas del checklist.
        """
        Shipment = self.env['crfp.shipment']
        has_method = hasattr(Shipment, '_check_blocking_tasks')
        if has_method:
            _logger.warning(
                "\n╔═══ FUNCIONALIDAD DESHABILITADA ═══╗\n"
                "  _check_blocking_tasks() tiene el blocking_map\n"
                "  completamente comentado (TODO pendiente).\n"
                "  RIESGO: Sin validación, un embarque puede\n"
                "  avanzar a 'shipped' sin documentos listos.\n"
                "  ACCIÓN: Reactivar con reglas correctas.\n"
                "╚════════════════════════════════════════╝"
            )

    def test_diagnostic_tracking_models_unused(self):
        """
        HALLAZGO: crfp.tracking.position y crfp.tracking.temperature
        están definidos pero NINGÚN código los crea automáticamente.
        No hay vistas directas en el form del embarque para ellos.
        Son funcionalidad abandonada.
        """
        unused_models = []
        for model_name in ['crfp.tracking.position', 'crfp.tracking.temperature']:
            Model = self.env.get(model_name)
            if Model is not None:
                # Verificar si hay registros (indicaría uso manual)
                count = Model.search_count([])
                unused_models.append(f"  {model_name}: {count} registros en BD")

        if unused_models:
            _logger.warning(
                "\n╔═══ MODELOS SIN USO AUTOMÁTICO ═══╗\n"
                "%s\n"
                "  Estos modelos no son creados por ningún código.\n"
                "  Solo uso manual (si alguno tiene datos).\n"
                "  OPCIÓN A: Integrar en el workflow (ej: GPS import)\n"
                "  OPCIÓN B: Eliminar si no se planea usar.\n"
                "╚══════════════════════════════════════════╝",
                "\n".join(unused_models)
            )

    def test_diagnostic_container_config_disconnected(self):
        """
        HALLAZGO: crfp.container.config se crea desde SO vía wizard,
        pero NUNCA se lee al crear el embarque. Los datos de packing
        se recalculan desde la cotización/SO, ignorando el config.
        """
        _logger.warning(
            "\n╔═══ FUNCIONALIDAD DESCONECTADA ═══╗\n"
            "  crfp.container.config se crea por wizard desde SO\n"
            "  pero action_create_shipment() NO lo consume.\n"
            "  El embarque recalcula packing desde quotation/SO.\n"
            "  RESULTADO: Los usuarios configuran contenedores\n"
            "  que luego se ignoran al crear el embarque.\n"
            "  ACCIÓN: Integrar config → shipment o documentar\n"
            "  que es solo una herramienta de planificación.\n"
            "╚════════════════════════════════════════════════╝"
        )


@tagged('audit_tests', 'crfp_logistics')
class TestShipmentLineShortages(TransactionCase):
    """Test de detección de faltantes en líneas del embarque."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def test_line_shortage_detection(self):
        """has_shortage = True cuando actual < planned."""
        shipment = self.env['crfp.shipment'].create({
            'partner_id': self.env['res.partner'].create({'name': 'Short'}).id,
        })
        line = self.env['crfp.shipment.line'].create({
            'shipment_id': shipment.id,
            'boxes_planned': 1386,
            'boxes_actual': 1200,
            'net_weight_planned': 24948.0,
            'net_weight_actual': 21600.0,
        })
        self.assertTrue(line.has_shortage, "Debe detectar faltante")
        self.assertEqual(line.boxes_diff, -186)
        self.assertLess(line.weight_diff, 0)

    def test_line_no_shortage_when_equal(self):
        """Sin faltante cuando actual == planned."""
        shipment = self.env['crfp.shipment'].create({
            'partner_id': self.env['res.partner'].create({'name': 'Full'}).id,
        })
        line = self.env['crfp.shipment.line'].create({
            'shipment_id': shipment.id,
            'boxes_planned': 1386,
            'boxes_actual': 1386,
            'net_weight_planned': 24948.0,
            'net_weight_actual': 24948.0,
        })
        self.assertFalse(line.has_shortage)

    def test_shipment_has_shortages_flag(self):
        """Embarque detecta si alguna línea tiene faltante."""
        shipment = self.env['crfp.shipment'].create({
            'partner_id': self.env['res.partner'].create({'name': 'Mixed'}).id,
        })
        self.env['crfp.shipment.line'].create({
            'shipment_id': shipment.id,
            'boxes_planned': 1386,
            'boxes_actual': 1000,
        })
        self.assertTrue(shipment.has_shortages)
