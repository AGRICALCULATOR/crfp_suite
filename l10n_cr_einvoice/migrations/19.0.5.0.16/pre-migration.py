"""Deactivate broken l10n_cr views BEFORE module data loads.

This pre-migration runs before Odoo validates views during upgrade.
Views referencing l10n_cr_document_id, l10n_cr_header_information,
or no_shipping cause validation errors in Odoo 19 because those
elements/fields were removed.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(env):
    env.cr.execute("""
        UPDATE ir_ui_view SET active = false
        WHERE active = true
          AND (
              (type = 'qweb' AND arch_db LIKE '%%l10n_cr_header_information%%')
              OR (type = 'qweb' AND arch_db LIKE '%%no_shipping%%'
                  AND key LIKE 'gen_key.%%')
              OR arch_db LIKE '%%l10n_cr_document_id%%'
          )
        RETURNING id, key
    """)
    rows = env.cr.fetchall()
    if rows:
        _logger.info(
            'Pre-migration: deactivated %d broken l10n_cr views: %s',
            len(rows), [r[1] for r in rows],
        )
