# CRFP Suite — CR Farm Products Odoo Modules

## Proyecto

Módulos Odoo 19 para CR Farm Products.

- **Repositorio:** AGRICALCULATOR/crfp_suite
- **Staging:** Odoo.sh → proyecto `agricalculator-odoo-crfarm`, rama `staging-test-modules`

## Módulos

| Módulo | Descripción |
|--------|-------------|
| `crfp_base` | Base compartida: tipos de documento, lógica común |
| `crfp_pricing` | Gestión de precios y tarifas |
| `crfp_logistics` | Logística y transporte |
| `crfp_claims` | Gestión de reclamos |

## Reglas de desarrollo Odoo 19

### Rutas HTTP
- Usar `type='jsonrpc'` en los decoradores `@http.route` (no `type='json'`).
- Ejemplo correcto: `@http.route('/crfp/endpoint', type='jsonrpc', auth='user')`

### XML — Vistas de formulario
- No usar el atributo `expand` en tags `<group>`.
- No usar `<separator/>` standalone innecesarios.

### XML — Search views
- No usar `<separator/>` dentro de `<search>`.
- No usar `<group string="...">` dentro de `<search>`.
- Los filtros van directamente como `<filter>` e `<group by="...">` sin wrapper de grupo con string.

## Flujo de trabajo

1. Desarrollar en rama feature.
2. Hacer PR hacia `main`.
3. Merge a `staging-test-modules` para probar en Odoo.sh.
