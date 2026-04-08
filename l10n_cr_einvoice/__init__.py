from . import models


_DISABLE_SQL = """
    UPDATE ir_ui_view SET active = false
    WHERE active = true
      AND (
          (type = 'qweb'
           AND key LIKE 'gen_key.%%'
           AND (arch_db LIKE '%%l10n_cr_header_information%%'
                OR name = 'report_invoice_document_add_pesos'))
          OR arch_db LIKE '%%l10n_cr_document_id%%'
      )
"""


def _pre_init_disable_broken_views(env_or_cr):
    """Deactivate orphan views BEFORE module data loads.

    Works whether Odoo passes an Environment or a raw cursor.
    Uses %% because cr.execute(sql, ()) triggers param substitution.
    """
    cr = getattr(env_or_cr, 'cr', env_or_cr)
    cr.execute(_DISABLE_SQL, ())


def _post_init_disable_broken_views(env_or_cr):
    """Second pass — catch any views re-activated during install."""
    cr = getattr(env_or_cr, 'cr', env_or_cr)
    cr.execute(_DISABLE_SQL, ())
