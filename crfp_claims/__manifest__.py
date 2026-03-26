{
    'name': 'CR Farm Claims - Export Claims Management',
    'version': '19.0.1.0.0',
    'category': 'Inventory/Logistics',
    'summary': 'Manage export claims: quality, temperature, shortage, damage',
    'description': """
        Claims management for CR Farm Products export operations.
        Track claims from customers or to carriers/insurance.
        Evidence, communication logs, resolution tracking.
    """,
    'author': 'CR Farm Products VYM S.A.',
    'website': 'https://crfarm.erpcr.net',
    'license': 'LGPL-3',
    'depends': ['crfp_base', 'crfp_logistics', 'mail'],
    'data': [
        'security/crfp_claims_security.xml',
        'security/ir.model.access.csv',
        'data/crfp_claim_sequence.xml',
        'views/crfp_claim_views.xml',
        'views/crfp_shipment_views.xml',
        'views/crfp_claims_menus.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
