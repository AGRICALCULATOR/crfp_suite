from . import models


def _post_init_disable_broken_views(env):
    """Deactivate broken l10n_cr views on fresh install.

    The _register_hook in ir_actions_report.py handles this on every server
    start, but this hook ensures it also runs during the initial install
    transaction before the server fully starts.
    """
    env.cr.execute("""
        UPDATE ir_ui_view SET active = false
        WHERE active = true
          AND (
              (type = 'qweb' AND arch_db LIKE '%%l10n_cr_header_information%%')
              OR (type = 'qweb' AND arch_db LIKE '%%no_shipping%%'
                  AND key LIKE 'gen_key.%%')
              OR arch_db LIKE '%%l10n_cr_document_id%%'
          )
    """)
