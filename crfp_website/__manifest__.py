{
    'name': 'CR Farm Website — Corporate Site & Lead Capture',
    'version': '19.0.1.0.0',
    'category': 'Website',
    'summary': 'Corporate website, product catalog, AI-powered lead capture and chatbot',
    'description': """
        CR Farm Products corporate website built on Odoo Website.

        Features:
        - Corporate pages: Home, About Us, Company History, Product Catalog, Contact
        - Lead capture form with automatic CRM integration
        - AI lead classification (priority, product interest, region) via Claude API
        - AI chatbot widget on all website pages
        - Cron job to auto-classify unclassified leads

        Configuration:
        - Set API key at Settings > Technical > Parameters > System Parameters
          Key: crfp_website.anthropic_api_key
    """,
    'author': 'CR Farm Products VYM S.A.',
    'website': 'https://crfarm.erpcr.net',
    'license': 'LGPL-3',
    'depends': ['website', 'crm', 'crfp_base', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/crfp_website_cron.xml',
        'views/website_crfarm_templates.xml',
        'views/crm_lead_views.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'crfp_website/static/src/css/crfp_chatbot.css',
            'crfp_website/static/src/js/crfp_chatbot.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
