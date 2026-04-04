{
    'name': 'CR Farm Website — Corporate B2B Site & Lead Capture',
    'version': '19.0.2.0.0',
    'category': 'Website',
    'summary': 'B2B corporate website, product catalog, AI-powered lead capture and chatbot',
    'description': """
        CR Farm Products corporate website built on Odoo Website.

        Features:
        - B2B corporate pages: Home, About Us, Company History, Product Catalog,
          Photo Gallery, Certifications, Contact
        - crfp.website.product model: full B2B technical spec sheets per product
          (scientific name, production season, packaging EU/USA/CA, formats, HS codes)
        - B2B lead capture form: company type, job title, import volume, incoterm preference
        - AI lead classification (priority, product interest, region) via Claude API
        - AI chatbot widget on all website pages
        - Hourly cron job to auto-classify unclassified leads
        - Gallery with lightbox, scroll-reveal animations, catalog category filter

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
        'data/crfp_website_product_data.xml',
        'views/crfp_website_product_views.xml',
        'views/website_crfarm_templates.xml',
        'views/crm_lead_views.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'crfp_website/static/src/css/crfp_website.css',
            'crfp_website/static/src/css/crfp_chatbot.css',
            'crfp_website/static/src/js/crfp_website.js',
            'crfp_website/static/src/js/crfp_chatbot.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
