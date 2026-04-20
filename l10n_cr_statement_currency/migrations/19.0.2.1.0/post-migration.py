"""Post-migration for 19.0.2.1.0: attach the statement PDF to every existing
follow-up mail template.

post_init_hook only fires on a fresh install. To make the same guarantee
for environments that already had the module installed (staging/production),
we run the same helper as a migration. Idempotent — skips templates that
already reference the report.
"""
from odoo.addons.l10n_cr_statement_currency.hooks import (
    _attach_statement_pdf_to_followup_templates,
)


def migrate(cr, version):
    from odoo.api import Environment
    from odoo import SUPERUSER_ID
    env = Environment(cr, SUPERUSER_ID, {})
    _attach_statement_pdf_to_followup_templates(env)
