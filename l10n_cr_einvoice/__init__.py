from . import models


def _pre_init_disable_broken_views(env):
    """Deactivate orphan views BEFORE module data loads.

    NOTE: cursor.execute() without a params tuple does NO %-substitution,
    so use single % in LIKE patterns (not %%).
    """
    env.cr.execute("""
        UPDATE ir_ui_view SET active = false
        WHERE active = true
          AND (
              (type = 'qweb'
               AND key LIKE 'gen_key.%'
               AND (arch_db LIKE '%l10n_cr_header_information%'
                    OR name = 'report_invoice_document_add_pesos'))
              OR arch_db LIKE '%l10n_cr_document_id%'
          )
    """)


def _post_init_disable_broken_views(env):
    """Second pass — catch any views re-activated during install."""
    _pre_init_disable_broken_views(env)
