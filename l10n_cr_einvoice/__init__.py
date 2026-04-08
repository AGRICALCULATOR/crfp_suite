from . import models


def _post_init_disable_broken_views(env):
    """Deactivate inherited invoice views with xpaths that don't exist in Odoo 19.

    Some l10n_cr or auto-generated views reference elements like
    'l10n_cr_header_information' or 'no_shipping' that were removed
    in Odoo 19's account.report_invoice_document template.
    """
    _disable_broken_invoice_views(env)


def _disable_broken_invoice_views(env):
    """SQL-based deactivation of views with broken xpaths for Odoo 19."""
    env.cr.execute("""
        UPDATE ir_ui_view SET active = false
        WHERE active = true
          AND type = 'qweb'
          AND (arch_db LIKE '%l10n_cr_header_information%'
               OR arch_db LIKE '%no_shipping%')
    """)
    env.cr.execute("SELECT count(*) FROM ir_ui_view WHERE active = false AND type = 'qweb' AND (arch_db LIKE '%l10n_cr_header_information%' OR arch_db LIKE '%no_shipping%')")
    count = env.cr.fetchone()[0]
    if count:
        import logging
        logging.getLogger(__name__).info(
            'Deactivated %d broken QWeb views (l10n_cr_header_information/no_shipping)', count
        )
