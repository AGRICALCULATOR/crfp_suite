# CRFP Suite — CR Farm Products Odoo 19 Enterprise (Odoo.sh)

## Proyecto

Modulos Odoo 19 para CR Farm Products, empresa exportadora agricola de Costa Rica.

- **Repositorio:** AGRICALCULATOR/crfp_suite
- **Staging:** Odoo.sh -> proyecto `agricalculator-odoo-crfarm`, rama `staging-test-modules`
- **URL Staging:** https://agricalculator-odoo-crfarm-staging-test-modules-30630647.dev.odoo.com

## Arquitectura de Modulos

```
crfp_claims -> crfp_logistics -> crfp_pricing -> crfp_base -> [base, sale, product, mail]
crfp_website -> crfp_base
invoice_weight (independiente)
l10n_cr_einvoice (independiente, FenixCR v4.4)
```

Flujo principal: `crfp.quotation` -> `sale.order` -> `crfp.shipment` (14 estados) -> `account.move`

## Reglas de Desarrollo Odoo 19

### Rutas HTTP
- Usar `type='jsonrpc'` en decoradores `@http.route` (no `type='json'`).
- Ejemplo: `@http.route('/crfp/endpoint', type='jsonrpc', auth='user')`

### XML — Vistas
- No usar atributo `expand` en `<group>`.
- No usar `<separator/>` standalone innecesarios.
- No usar `<separator/>` ni `<group string="...">` dentro de `<search>`.

### Flujo de trabajo
1. Desarrollar en rama feature.
2. PR hacia `main`.
3. Merge a `staging-test-modules` para probar en Odoo.sh.

---

## REGLAS DE NEGOCIO CRITICAS

### Flujo Semanal de Pricing
1. **Miercoles**: Compradores de campo actualizan `raw_price_crc` via portal movil (`/crfp/prices/<token>`)
2. **Jueves**: Vendedor abre AgriPrice Calculator -> carga cotizacion anterior del historial -> la duplica -> precios se recalculan con precios de campo actualizados + tipo de cambio actual -> envia lista de precios al cliente
3. **Cliente ordena via WhatsApp**: Envia su orden en pallets (ej. "5 pallets yuca, 3 pallets ginger"). Vendedor llena los pallets directamente en el formulario de la cotizacion (los campos son editables)
4. **Crear SO**: Con pallets ya llenos, se crea SO desde la cotizacion con "Create Sale Order"

**IMPORTANTE**: Al crear la cotizacion/lista de precios, pallets=0 es CORRECTO y es el flujo normal — el vendedor aun no sabe cuantos pallets pide el cliente. Los pallets se llenan manualmente en el formulario Odoo DESPUES de recibir la orden del cliente. Este flujo ya funciona correctamente, NO es un bug.

### Principios del Calculator (NO cambiar el diseno)
- La calculadora JS/OWL (`calculator_service.js` + `crfp_calculator.js`) es el motor de calculo principal
- Los campos de precio en `crfp.quotation.line` son Float planos (NO computed). La calculadora JS los escribe via `/crfp/api/quotation/save`
- Se necesita un backup Python de la logica de calculo para automacion servidor (cron, duplicacion semanal)
- Las lineas en borradores SI deben actualizarse cuando cambia el tipo de cambio
- Las cotizaciones confirmadas/enviadas QUEDAN CONGELADAS — no se recalculan

### Cadena de Calculo (replicar EXACTAMENTE en Python)

```
raw_price_crc (CRC)
  --[formula compra]--> purchase_cost (USD)
  + packing_cost (formula empaque)
  + profit
  = exw_price (USD)
  + logistics_per_box (freight + costos segun incoterm)
  = final_price (USD/caja)
```

**Formulas de compra** (`purchase_formula`):
- `standard`: `(net_kg * raw_price_crc) / exchange_rate`
- `quintal`: `(1 * net_kg / 46) * (raw_price_crc / exchange_rate)`

**Formulas de empaque** (`calc_type`, donde `txk = labor_per_kg + materials_per_kg + indirect_per_kg`):
- `standard`: `(txk * net_kg) + box_cost`
- `flat_no_box`: `txk` (coco seco)
- `flat_plus_box`: `txk + box_cost` (coco verde, cana caja)
- `kg_no_box`: `txk * net_kg` (calabaza bolsa)

**Peso bruto** (`gross_weight_type`):
- `standard`: `net_kg * 2.2 + 2` (tare 2 lbs)
- `no_tare`: `net_kg * 2.2`
- `zero`: `0` (coco)

**Logistica por caja:**
- Freight SIEMPRE se suma: `all_in_freight / total_boxes`
- Costos fijos con `inc_*=True` en freight_quote se ponen en $0 (ya incluidos en flete)
- Incoterm matrix controla solo costos de DESTINO + seguro + duties
- Seguro: `exw_price * (insurance_pct / 100)` si incoterm lo incluye
- Duties: `(exw_price + freight_per_box + insurance_per_box) * (duties_pct / 100)` si DDP

### Tipo de Cambio
- Pipeline: xe.com → Odoo Contabilidad (res.currency.rate) → crfp.settings.exchange_rate → snapshot en cotizacion
- `exchange_rate`: campo Float plano (default=503.0) — NO computed (se cambio en Fase 1 porque computed retornaba 0 al actualizar modulo)
- `exchange_rate_source`: Selection (auto/manual) — auto lee de res.currency.rate
- Sincronizar: boton "Sincronizar Tipo de Cambio" en Settings o cron diario
- `_get_odoo_exchange_rate()`: lee `inverse_company_rate` de USD, fallback a res.currency.rate
- Cron: `_cron_update_exchange_rate()` a las 02:00 UTC (solo registros con source=auto)
- Cada cotizacion guarda snapshot al crearse
- Borradores: se recalculan automaticamente al cambiar TC (write() override en crfp.quotation)
- Confirmadas: congeladas — NO se recalculan
- Configurar en Odoo: Contabilidad → Configuracion → Monedas → Tasas automaticas (xe.com, diario)

### Price Lists vs Quotations
- **Quotations** (`crfp.quotation`): Personalizadas por cliente, con pesos/margenes/ganancias distintas
- **Price Lists** (`crfp.price.list`): Para web (Fase 2), generales por pais
- Son modelos SEPARADOS — no confundir

---

## FASE 1 COMPLETADA — Correcciones aplicadas

| ID | Estado | Correccion aplicada |
|----|--------|---------------------|
| BP-01 | HECHO | `_compute_all_prices()` en crfp_quotation_line.py — replica calcSingleProduct() del JS |
| BP-02 | HECHO | write() override en crfp_quotation.py recalcula drafts al cambiar TC |
| BP-04 | HECHO | write() override en crfp_product.py propaga raw_price_crc a lineas draft |
| BP-05 | HECHO | action_create_sale_order() usa lista filtrada 1:1 en vez de enumerate |
| BP-06 | FASE 2 | Cron detecta price lists activas al cambiar TC (solo log, recalculo pendiente Fase 2) |
| BP-07 | HECHO | @api.onchange('freight_quote_id') recalcula lineas |
| BP-08 | HECHO | @api.onchange('incoterm') recalcula lineas |
| BP-09 | OK | partner_id ya se guarda correctamente como integer en JS/API |
| BP-10 | HECHO | pricing_api.py lee de crfp.settings en vez de crfp.fixed.cost |
| BP-11 | HECHO | CSS fuerza light theme en calculator (no dark theme) |

---

## MODELOS CLAVE

### crfp.settings (Singleton, crfp_base)
- `exchange_rate`: Float(12,2) default=503.0 — campo plano, sincronizado via boton o cron
- `exchange_rate_source`: Selection(auto/manual)
- `fc_*_default`: 9 campos costos fijos por defecto (USD/contenedor) — fuente unica (crfp.fixed.cost eliminado)
- `default_total_boxes`: 1386
- `price_validity_days`: 7
- Acceso: `crfp.settings.get_settings()`
- API: `pricing_api.py` lee de settings (no de crfp.fixed.cost)

### crfp.product (crfp_base)
- `raw_price_crc`: Precio campo en colones (lo actualiza comprador via portal)
- `calc_type`: standard / flat_no_box / flat_plus_box / kg_no_box
- `purchase_formula`: standard / quintal
- `gross_weight_type`: standard / no_tare / zero
- `product_id`: Many2one(product.product) — link a SKU Odoo
- 18 productos semilla (yuca, malanga, eddoes, ginger, coco, cana, calabaza)

### crfp.quotation (crfp_pricing)
- `state`: draft -> confirmed -> sent -> won -> lost
- `exchange_rate`: snapshot al crear
- `fc_*`: snapshots costos fijos
- `partner_id`: Many2one(res.partner) — REQUERIDO para crear SO
- `freight_quote_id`: Many2one(crfp.freight.quote)
- `incoterm`: Selection (EXW..DDP), default FOB

### crfp.quotation.line (crfp_pricing)
- Precios: `purchase_cost`, `packing_cost`, `exw_price`, `logistics_per_box`, `final_price` — Float planos (JS los escribe)
- Config: `raw_price_crc`, `net_kg`, `box_cost`, `labor_per_kg`, `materials_per_kg`, `indirect_per_kg`, `profit`
- Orden: `pallets`, `boxes_per_pallet`, `total_boxes`(computed), `line_total`(computed)
- `include_in_pdf`: Boolean — excluye de totales, SO y PDF si False
- `product_id`: Many2one(product.product) — SKU por linea (NO heredado del producto)

### crfp.freight.quote (crfp_pricing)
- `all_in_freight`: Float — total flete USD (todo incluido)
- `inc_*`: 6 Booleans — que costos fijos ya incluye el flete
- `state`: draft -> active -> expired (cron auto-expire)

### crfp.incoterm.matrix (crfp_base)
- 9 incoterms (EXW a DDP) con 11 flags booleanos
- Datos semilla FIJOS — no modificar sin analizar impacto en calculator

### crfp.pallet.config (crfp_base)
- Matching por `product_keyword` (texto, NO foreign key) + `weight_kg`
- 14 configuraciones semilla

## Notas Tecnicas

- `product_id` en `crfp.quotation.line` es POR LINEA — un producto base puede tener multiples SKUs
- Pesos cruzan frontera de modulos: shipment -> invoice (`peso_neto`/`peso_total` vs `fp_net_weight`/`fp_gross_weight`)
- `crfp.pallet.config` usa matching por keyword, NO por foreign key
- El endpoint `/crfp/api/quotation/save` es critico — es lo que usa el calculator
- `_compute_all_prices()` en `crfp_quotation_line.py` replica EXACTAMENTE las formulas del JS (`calculator_service.js`)
- Todos los costos fijos son USD/contenedor, se dividen entre `total_boxes` para obtener costo por caja
- Owl: NO usar `t-model.number` en Odoo 19 — usar `t-att-value` + `t-on-input` (t-model falla silenciosamente)
- CSS: Calculator fuerza light theme via `html.dark .crfp-app` overrides

## Proteccion de Templates (Rebuilds Odoo.sh)

- `l10n_cr_einvoice/data/ensure_base_template_active.xml` — previene desactivacion del template base de factura durante rebuilds
- **NUNCA** modificar `l10n_cr_einvoice/` sin verificar impacto en facturacion electronica
- Al hacer cherry-pick o merge, siempre verificar con `git diff-tree --name-only` que no se toquen archivos de facturacion
