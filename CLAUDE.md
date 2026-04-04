# CR Farm Products - Export Suite (crfp_suite)

## Proyecto
Módulos Odoo 19 Enterprise para gestión de precios de exportación y logística.

## Módulos
- **crfp_base** - Datos maestros (puertos, carriers, productos, cajas, pallets, incoterms)
- **crfp_pricing** - Calculadora de precios con UI Owl personalizada + integración con Ventas
- **crfp_claims** - Gestión de reclamaciones
- **crfp_logistics** - Logística de exportación

## Stack técnico
- Odoo 19 Enterprise
- Python 3 (modelos ORM)
- JavaScript/OWL (componentes frontend)
- XML (vistas, datos, seguridad)

## Convenciones
- Prefijo de módulos: `crfp_`
- Rutas JSON-RPC: usar `type="jsonrpc"` (no `type="json"`) para Odoo 19
- Seguir estructura estándar de módulos Odoo: models/, views/, security/, data/, static/

## Comandos útiles
```bash
# Reiniciar Odoo con actualización de módulo
./odoo-bin -u crfp_base,crfp_pricing -d <database> --stop-after-init

# Ver logs en tiempo real
tail -f /var/log/odoo/odoo.log
```
