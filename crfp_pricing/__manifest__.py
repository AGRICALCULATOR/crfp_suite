{
    'name': 'CR Farm Products - Export Pricing Calculator',
    'version': '19.0.2.0.0',
    'category': 'Sales/Export',
    'summary': 'Export price calculator with custom Owl UI, PDF quotes and Sales integration',
    'description': """
        Price calculator for CR Farm Products export operations.
        Custom Owl frontend — AgriPrice Calculator.
        PDF quotation reports, email sending, Sales integration.
    """,
    'author': 'CR Farm Products VYM S.A.',
    'website': 'https://crfarm.erpcr.net',
    'license': 'LGPL-3',
    'depends': ['crfp_base', 'sale_management', 'mail'],
    'data': [
        'security/crfp_pricing_security.xml',
        'security/ir.model.access.csv',
        'views/crfp_freight_quote_views.xml',
        'views/crfp_quotation_views.xml',
        'views/crfp_pricing_menus.xml',
        'report/crfp_quotation_report.xml',
        'data/mail_template_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'crfp_pricing/static/src/css/crfp_calculator.css',
            'crfp_pricing/static/src/js/calculator_service.js',
            'crfp_pricing/static/src/js/product_card.js',
            'crfp_pricing/static/src/js/crfp_calculator.js',
            'crfp_pricing/static/src/xml/product_card.xml',
            'crfp_pricing/static/src/xml/crfp_calculator.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
