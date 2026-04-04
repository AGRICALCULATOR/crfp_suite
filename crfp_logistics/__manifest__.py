{
    'name': 'CR Farm Logistics - Export Shipment Management',
    'version': '19.0.1.0.0',
    'category': 'Inventory/Logistics',
    'summary': 'Export shipment management: containers, documents, tracking, packing lists',
    'description': """
        Export logistics module for CR Farm Products.
        Manages shipments, containers, bookings, documents, tracking and packing lists.
        Works alongside crfp_pricing without modifying it.
    """,
    'author': 'CR Farm Products VYM S.A.',
    'website': 'https://crfarm.erpcr.net',
    'license': 'LGPL-3',
    'depends': ['crfp_base', 'crfp_pricing', 'sale_management', 'mail'],
    'data': [
        'security/crfp_logistics_security.xml',
        'security/ir.model.access.csv',
        'data/crfp_shipment_sequence.xml',
        'data/crfp_checklist_template_data.xml',
        'data/crfp_document_type_data.xml',
        'data/crfp_alert_cron.xml',
        'report/crfp_packing_list_report.xml',
        'wizard/container_config_wizard_views.xml',
        'views/crfp_shipment_views.xml',
        'views/crfp_booking_views.xml',
        'views/crfp_document_views.xml',
        'views/crfp_checklist_template_views.xml',
        'views/crfp_tracking_views.xml',
        'views/crfp_container_config_views.xml',
        'views/sale_order_views.xml',
        'views/crfp_logistics_menus.xml',
        'views/crfp_container_config_menus.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
