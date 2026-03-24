{
    'name': 'CR Farm Products - Export Pricing Calculator',
    'version': '19.0.1.0.0',
    'category': 'Sales/Export',
    'summary': 'Export price calculator with custom Owl UI and Sales integration',
    'description': """
        Price calculator for CR Farm Products export operations.
        Custom Owl frontend that replicates the AgriPrice Calculator.
        Integrated with Odoo Sales for quotation/order creation.
    """,
    'author': 'CR Farm Products VYM S.A.',
    'website': 'https://crfarm.erpcr.net',
    'license': 'LGPL-3',
    'depends': ['crfp_base', 'sale_management'],
    'data': [
        'security/crfp_pricing_security.xml',
        'security/ir.model.access.csv',
        'views/crfp_freight_quote_views.xml',
        'views/crfp_quotation_views.xml',
        'views/crfp_pricing_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'crfp_pricing/static/src/css/crfp_calculator.css',
            'crfp_pricing/static/src/js/calculator_service.js',
            'crfp_pricing/static/src/js/product_card.js',
            'crfp_pricing/static/src/js/price_calculator.js',
            'crfp_pricing/static/src/js/logistics_setup.js',
            'crfp_pricing/static/src/js/box_cost_manager.js',
            'crfp_pricing/static/src/js/confirm_order.js',
            'crfp_pricing/static/src/js/price_history.js',
            'crfp_pricing/static/src/js/crfp_calculator.js',
            'crfp_pricing/static/src/xml/product_card.xml',
            'crfp_pricing/static/src/xml/price_calculator.xml',
            'crfp_pricing/static/src/xml/logistics_setup.xml',
            'crfp_pricing/static/src/xml/box_cost_manager.xml',
            'crfp_pricing/static/src/xml/confirm_order.xml',
            'crfp_pricing/static/src/xml/price_history.xml',
            'crfp_pricing/static/src/xml/crfp_calculator.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
