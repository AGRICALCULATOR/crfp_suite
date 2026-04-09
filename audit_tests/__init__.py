# audit_tests — Diagnóstico funcional de la suite crfp_suite
# Ejecutar con: odoo-bin --test-tags=audit_tests -d <db> --stop-after-init
#
# Estos tests verifican flujos funcionales Y detectan:
#   - Campos duplicados o sin usar
#   - Métodos huérfanos (definidos pero nunca llamados)
#   - Inconsistencias entre módulos
#   - Código muerto
#   - Problemas de integración
