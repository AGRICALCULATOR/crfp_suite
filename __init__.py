# Tipos_de_cambio

Módulo para Odoo 19 que actualiza los tipos de cambio de **USD** y **EUR** desde el API del **Ministerio de Hacienda (Costa Rica)**.

> Nota: el nombre técnico del módulo es `tipos_cambio_bccr` por compatibilidad.

## Funcionalidad

- Consulta el API de Hacienda para obtener:
  - **USD** desde `venta.valor`.
  - **EUR** desde `colones`.
- Actualiza exclusivamente USD y EUR para evitar conflictos con la moneda base CRC.
- Ejecuta una tarea programada (`ir.cron`) para actualizar los tipos de cambio.

## Instalación

1. Copie la carpeta `tipos_cambio_bccr` en su ruta de addons.
2. Actualice la lista de aplicaciones en Odoo.
3. Instale el módulo **Tipo de Cambio Hacienda CR (Odoo 19)**.

## Configuración en Contabilidad

Ahora el módulo agrega una sección propia dentro de:

- **Ajustes → Contabilidad → Divisas → Tipo de Cambio Hacienda**

Opciones disponibles:

- **Actualizar automáticamente**: activa/desactiva la ejecución automática para la compañía actual.
- **Intervalo (días)**: cada cuántos días se ejecuta el cron.
- **Última sincronización**: fecha/hora del último intento exitoso.
- **Actualizar ahora**: botón para ejecutar la sincronización manual en el momento.

## ¿Cómo validar que está funcionando?

1. Presione **Actualizar ahora** en la sección anterior.
2. Revise las tasas en **Contabilidad → Configuración → Monedas** para **USD** y **EUR**.
3. Verifique el log del servidor Odoo. Deben aparecer entradas como:
   - `Hacienda: USD actualizado a ...`
   - `Hacienda: EUR actualizado a ...`

Si no ve cambios, confirme:

- Que existan las monedas USD y EUR activas en la base de datos.
- Que el servidor tenga salida a internet hacia `api.hacienda.go.cr`.
- Que la opción **Actualizar automáticamente** esté activa para su compañía.

## ¿Dónde se selecciona y cómo se prueba?

No hay un selector adicional dentro de este módulo para elegir monedas o proveedor.
El módulo está diseñado para actualizar **solamente USD y EUR** desde Hacienda.

Para probarlo manualmente en Odoo:

1. Active el modo desarrollador.
2. Vaya a **Ajustes → Técnico → Automatización → Acciones planificadas**.
3. Abra **Hacienda CR: Actualizar Tipo de Cambio**.
4. Presione **Ejecutar manualmente** (Run Manually).

Cómo validar que está funcionando:

- Revise las tasas en **Contabilidad → Configuración → Monedas** para **USD** y **EUR**.
- Verifique el log del servidor Odoo. Deben aparecer entradas como:
  - `Hacienda: USD actualizado a ...`
  - `Hacienda: EUR actualizado a ...`

Si no ve cambios, confirme:

- Que existan las monedas USD y EUR activas en la base de datos.
- Que el servidor tenga salida a internet hacia `api.hacienda.go.cr`.
- Que la acción planificada esté activa.

## Nota técnica

Los valores consultados (USD y EUR) se escriben en `res.currency.rate` usando el campo `inverse_company_rate` para la fecha actual y cada compañía.
