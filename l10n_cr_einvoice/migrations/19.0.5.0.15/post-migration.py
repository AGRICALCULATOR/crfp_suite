"""Deactivate broken QWeb views referencing l10n_cr_header_information / no_shipping."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("""
        UPDATE ir_ui_view SET active = false
        WHERE active = true
          AND type = 'qweb'
          AND (arch_db LIKE '%l10n_cr_header_information%'
               OR arch_db LIKE '%no_shipping%')
        RETURNING id, key
    """)
    rows = cr.fetchall()
    if rows:
        _logger.info(
            'Deactivated %d broken QWeb views: %s',
            len(rows), [r[1] for r in rows],
        )
