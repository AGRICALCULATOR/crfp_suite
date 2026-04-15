{
    'name': 'CR Farm Multi-Currency Reports',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Currency selector for ALL standard Odoo accounting reports',
    'description': """
        Adds a currency filter dropdown to standard Odoo accounting reports.
        When a foreign currency is selected (e.g., USD), the report shows
        amounts in the original transaction currency (amount_currency field),
        NOT reconverted amounts.
    """,
    'author': 'CR Farm Products S.A.',
    'website': 'https://www.crfarmexport.com',
    'license': 'LGPL-3',
    'depends': [
        'account_reports',
        'account',
    ],
    'data': [
        'views/account_report_views.xml',
        'data/account_report_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'crfp_multicurrency_reports/static/src/js/currency_filter.js',
            'crfp_multicurrency_reports/static/src/xml/currency_filter.xml',
        ],
    },
    'installable': True,
    'auto_install': False,
}
