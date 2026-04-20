{
    "name": "Costa Rica - Estado de cuenta (moneda original)",
    "summary": "Estado de cuenta de clientes por moneda original con PDF profesional",
    "description": """
Estado de cuenta por cobrar en moneda original (Odoo 19)
========================================================

- Reporte dinámico con agrupación por cliente y moneda original.
- Columna de días vencidos, subtotales por moneda y sección de pagos sin aplicar.
- Plantilla QWeb propia para el PDF con:
    * Datos del cliente y de la empresa
    * Tabla de facturas por moneda con días vencidos
    * Resumen de antigüedad (aging)
    * Saldos netos por moneda
- Envío por correo desde la ficha del contacto con plantilla editable.
""",
    "version": "19.0.2.1.0",
    "category": "Accounting/Accounting",
    "license": "LGPL-3",
    "author": "FenixCR Solutions",
    "depends": ["base", "account", "account_reports", "mail", "account_followup"],
    "assets": {
        "web.report_assets_common": [
            "l10n_cr_statement_currency/static/src/scss/account_report_original_currency.scss",
            "l10n_cr_statement_currency/static/src/scss/statement_pdf.scss",
        ],
    },
    "data": [
        "security/ir.model.access.csv",
        "data/account_report.xml",
        "reports/statement_paperformat.xml",
        "reports/statement_report.xml",
        "reports/statement_report_templates.xml",
        "views/res_partner_views.xml",
        "views/statement_send_wizard_views.xml",
    ],
    "installable": True,
    "application": False,
    "post_init_hook": "post_init_hook",
}
