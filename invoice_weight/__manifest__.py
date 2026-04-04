{
    'name': 'Invoice Weight',
    'version': '19.0.1.0.0',
    'category': 'Sales',
    'summary': 'Add net and total weight fields to sale and invoice lines',
    'description': """
        Adds peso_neto (net weight) and peso_total (gross weight) fields
        to sale.order.line and account.move.line for export logistics documents.
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
