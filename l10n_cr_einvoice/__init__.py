from . import models


_DISABLE_BROKEN_VIEWS_SQL = """
    UPDATE ir_ui_view SET active = false
    WHERE active = true
      AND (
          (type = 'qweb' AND arch_db LIKE '%%l10n_cr_header_information%%')
          OR (type = 'qweb' AND arch_db LIKE '%%no_shipping%%'
              AND key LIKE 'gen_key.%%')
          OR arch_db LIKE '%%l10n_cr_document_id%%'
      )
"""


def _pre_init_disable_broken_views(env):
    """Deactivate broken l10n_cr views BEFORE module data loads.

    Must run before Odoo validates views, otherwise views referencing
    l10n_cr_document_id (removed in Odoo 19) cause validation errors
    that fail the build on Odoo.sh.
    """
    env.cr.execute(_DISABLE_BROKEN_VIEWS_SQL)


def _post_init_disable_broken_views(env):
    """Second pass after install — catch any views created during install."""
    env.cr.execute(_DISABLE_BROKEN_VIEWS_SQL)
