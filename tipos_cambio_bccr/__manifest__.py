{
    'name': 'Tipo de Cambio Hacienda CR (Odoo 19)',
    'version': '19.0.3.0.0',
    'summary': 'Actualización de tipos de cambio USD y EUR desde Hacienda de Costa Rica',
    'category': 'Accounting',
    'author': 'FenixCR Solutions',
    'license': 'LGPL-3',
    'depends': ['account'],
    'external_dependencies': {'python': ['requests']},
    'data': [
        'data/ir_cron.xml',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'application': False,
}
