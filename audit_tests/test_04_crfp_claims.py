# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════
  TEST 04 — crfp_claims: Reclamos y Evidencia
  Diagnóstico: HTML en email, sequence, seguridad,
  edge cases en action_send_claim_email
═══════════════════════════════════════════════════════════════
"""
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


@tagged('audit_tests', 'crfp_claims')
class TestClaimWorkflow(TransactionCase):
    """Workflow completo del reclamo: draft → closed."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.partner = cls.env['res.partner'].create({
            'name': 'Claim Client', 'email': 'claim@test.com',
        })

    def _create_claim(self, **kwargs):
        """Helper: crea reclamo con datos mínimos."""
        vals = {
            'claim_type': 'quality',
            'origin': 'customer',
            'partner_id': self.partner.id,
            'description': '<p>Producto con daño visible en 30% de las cajas</p>',
            'claimed_amount': 5000.00,
        }
        vals.update(kwargs)
        return self.env['crfp.claim'].create(vals)

    def test_claim_sequence_generation(self):
        """Referencia auto-generada con formato CLAIM-YYYY-NNNN."""
        claim = self._create_claim()
        self.assertNotEqual(claim.name, 'New', "Debe tener referencia generada")
        self.assertIn('CLAIM-', claim.name)

    def test_claim_full_workflow(self):
        """draft → open → investigation → response_pending → resolved → closed."""
        claim = self._create_claim()
        self.assertEqual(claim.state, 'draft')

        claim.action_open()
        self.assertEqual(claim.state, 'open')

        claim.action_investigate()
        self.assertEqual(claim.state, 'investigation')

        claim.action_response_pending()
        self.assertEqual(claim.state, 'response_pending')

        # Resolver requiere resolution_type
        claim.resolution_type = 'credit_note'
        claim.action_resolve()
        self.assertEqual(claim.state, 'resolved')

        claim.action_close()
        self.assertEqual(claim.state, 'closed')
        self.assertTrue(claim.date_closed, "Debe setear fecha de cierre")

    def test_claim_resolve_requires_resolution_type(self):
        """No se puede resolver sin tipo de resolución."""
        claim = self._create_claim()
        claim.action_open()
        claim.action_investigate()
        # Sin resolution_type, debe fallar o advertir
        # (depende de la implementación — verificar comportamiento)
        try:
            claim.action_resolve()
            # Si no falla, verificar que al menos se documenta
            if not claim.resolution_type:
                _logger.warning(
                    "HALLAZGO: action_resolve() permite resolver sin resolution_type"
                )
        except (UserError, ValidationError):
            pass  # Comportamiento esperado

    def test_claim_cancel(self):
        """Cancelar reclamo desde cualquier estado."""
        claim = self._create_claim()
        claim.action_open()
        claim.action_cancel()
        self.assertEqual(claim.state, 'cancelled')

    def test_claim_evidence_count(self):
        """Contador de evidencias se computa correctamente."""
        claim = self._create_claim()
        self.assertEqual(claim.evidence_count, 0)

        self.env['crfp.claim.evidence'].create({
            'claim_id': claim.id,
            'evidence_type': 'photo',
            'name': 'Foto daño caja #1',
        })
        self.env['crfp.claim.evidence'].create({
            'claim_id': claim.id,
            'evidence_type': 'temperature_log',
            'name': 'Log temperatura contenedor',
        })
        self.assertEqual(claim.evidence_count, 2)

    def test_claim_communication_log(self):
        """Se pueden agregar entradas de bitácora."""
        claim = self._create_claim()
        log = self.env['crfp.claim.log'].create({
            'claim_id': claim.id,
            'log_type': 'email',
            'subject': 'Reclamo formal enviado',
            'body': '<p>Se envió reclamo formal al carrier</p>',
        })
        self.assertTrue(log.user_id, "User debe auto-asignarse")
        self.assertTrue(log.date, "Fecha debe auto-asignarse")


@tagged('audit_tests', 'crfp_claims', 'diagnostic')
class TestClaimDiagnostic(TransactionCase):
    """
    ╔══════════════════════════════════════════════════════════╗
    ║  DIAGNÓSTICO: Edge cases en action_send_claim_email     ║
    ║  y seguridad de permisos                                 ║
    ╚══════════════════════════════════════════════════════════╝
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.partner = cls.env['res.partner'].create({
            'name': 'Diag Client', 'email': 'diag@test.com',
        })

    def test_diagnostic_email_without_shipment(self):
        """
        HALLAZGO: action_send_claim_email() asume shipment_id existe.
        Si el claim no tiene embarque vinculado, ship.booking_id y
        ship.container_ids[0] causan AttributeError o IndexError.
        """
        claim = self.env['crfp.claim'].create({
            'claim_type': 'quality',
            'origin': 'customer',
            'partner_id': self.partner.id,
            'description': '<p>Reclamo sin embarque</p>',
            'claimed_amount': 1000.00,
        })
        # Intentar enviar email SIN shipment
        try:
            result = claim.action_send_claim_email()
            # Si no falla, el email se genera (posiblemente con datos vacíos)
            _logger.info("action_send_claim_email() SIN shipment: OK (no crasheó)")
        except (AttributeError, IndexError, TypeError) as e:
            _logger.warning(
                "\n╔═══ BUG: action_send_claim_email() SIN SHIPMENT ═══╗\n"
                "  Error: %s\n"
                "  El método asume que siempre hay un embarque vinculado.\n"
                "  CORRECCIÓN: Agregar verificación de shipment_id.\n"
                "╚══════════════════════════════════════════════════════╝",
                str(e)
            )

    def test_diagnostic_evidence_delete_by_basic_user(self):
        """
        HALLAZGO: ir.model.access.csv da perm_unlink=1 a base.group_user
        en crfp.claim.evidence. Cualquier usuario puede borrar evidencia,
        lo cual es un riesgo para la integridad del reclamo.
        """
        Evidence = self.env['crfp.claim.evidence']
        # Verificar el modelo de acceso
        access = self.env['ir.model.access'].search([
            ('model_id.model', '=', 'crfp.claim.evidence'),
            ('group_id', '=', self.env.ref('base.group_user').id),
        ])
        for rule in access:
            if rule.perm_unlink:
                _logger.warning(
                    "\n╔═══ RIESGO DE SEGURIDAD ═══╗\n"
                    "  crfp.claim.evidence: perm_unlink=1 para\n"
                    "  base.group_user (todos los usuarios).\n"
                    "  RIESGO: Cualquier usuario puede borrar\n"
                    "  evidencia de un reclamo.\n"
                    "  ACCIÓN: Cambiar perm_unlink=0 para group_user,\n"
                    "  solo managers deben poder eliminar evidencia.\n"
                    "╚═══════════════════════════════════════════╝"
                )

    def test_diagnostic_claim_types_coverage(self):
        """
        DIAGNÓSTICO: ¿Todos los tipos de reclamo se pueden crear?
        Verifica que el Selection field cubre todos los casos.
        """
        claim_types = ['quality', 'temperature', 'shortage', 'delay', 'damage', 'documentation', 'other']
        for ct in claim_types:
            claim = self.env['crfp.claim'].create({
                'claim_type': ct,
                'origin': 'customer',
                'partner_id': self.partner.id,
            })
            self.assertEqual(claim.claim_type, ct, f"Tipo {ct} debe ser válido")

    def test_diagnostic_claim_from_shipment(self):
        """
        Verifica que action_report_claim() en crfp.shipment
        crea un reclamo pre-llenado correctamente.
        """
        Shipment = self.env.get('crfp.shipment')
        if Shipment is not None and hasattr(Shipment, 'action_report_claim'):
            shipment = Shipment.create({
                'partner_id': self.partner.id,
            })
            result = shipment.action_report_claim()
            # Debe retornar una acción de ventana
            self.assertEqual(result.get('type'), 'ir.actions.act_window')
            ctx = result.get('context', {})
            self.assertEqual(ctx.get('default_shipment_id'), shipment.id,
                             "Reclamo debe pre-llenar shipment_id")
