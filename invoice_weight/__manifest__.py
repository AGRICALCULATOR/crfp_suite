{
    'name': 'Invoice Weight (Deprecated)',
    'version': '19.0.2.0.0',
    'category': 'Sales',
    'summary': 'Deprecated — weight fields consolidated into l10n_cr_einvoice',
    'description': """
        This module previously added peso_neto and peso_total fields to
        sale.order.line and account.move.line. Those fields are now handled
        by l10n_cr_einvoice (fp_net_weight / fp_gross_weight).

        This module is kept as an empty shell to avoid uninstall issues.
        It can be safely uninstalled from the UI when convenient.
    """,
    'author': 'CR Farm Products VYM S.A.',
    'license': 'LGPL-3',
    'depends': ['sale', 'account'],
    'data': [
        'views/sale_order_views.xml',
        'views/account_move_views.xml',
    ],
    'installable': True,
    'auto_install': False,
}
