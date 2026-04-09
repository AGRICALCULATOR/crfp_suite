# Audit Tests — CRFP Suite Odoo 19

## Ejecución

### Todos los tests de auditoría
```bash
odoo-bin --test-tags=audit_tests -d crfp_db --stop-after-init --log-level=warn
```

### Por módulo específico
```bash
# Solo crfp_base
odoo-bin --test-tags=crfp_base -d crfp_db --stop-after-init

# Solo crfp_pricing
odoo-bin --test-tags=crfp_pricing -d crfp_db --stop-after-init

# Solo crfp_logistics
odoo-bin --test-tags=crfp_logistics -d crfp_db --stop-after-init

# Solo crfp_claims
odoo-bin --test-tags=crfp_claims -d crfp_db --stop-after-init

# Solo crfp_website
odoo-bin --test-tags=crfp_website -d crfp_db --stop-after-init

# Solo tests cross-module
odoo-bin --test-tags=cross_module -d crfp_db --stop-after-init
```

### Solo tests de diagnóstico (hallazgos)
```bash
odoo-bin --test-tags=diagnostic -d crfp_db --stop-after-init --log-level=warn
```

## Estructura de archivos

| Archivo | Módulo | Tests | Diagnósticos |
|---------|--------|-------|-------------|
| test_01_crfp_base.py | crfp_base | 10 | 5 |
| test_02_crfp_pricing.py | crfp_pricing | 10 | 4 |
| test_03_crfp_logistics.py | crfp_logistics | 10 | 5 |
| test_04_crfp_claims.py | crfp_claims | 7 | 4 |
| test_05_crfp_website.py | crfp_website | 5 | 4 |
| test_06_cross_module.py | Integración | 1 | 5 |

## Cómo leer los resultados

Los tests de diagnóstico emiten WARNING con formato visual:
```
╔═══ HALLAZGO: DESCRIPCIÓN ═══╗
  Detalle del problema...
  ACCIÓN: Qué hacer para corregirlo
╚══════════════════════════════╝
```

Busca estos patrones en el log para encontrar todos los hallazgos.
