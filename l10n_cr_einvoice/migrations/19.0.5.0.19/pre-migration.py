"""Deactivate broken l10n_cr views — fix arch_db::text cast for Odoo 19 jsonb.

In Odoo 19, arch_db is jsonb, not text. LIKE requires explicit ::text cast.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("""
        UPDATE ir_ui_view SET active = false
        WHERE active = true
          AND (
              (type = 'qweb'
               AND key LIKE 'gen_key.%%'
               AND (arch_db::text LIKE '%%l10n_cr_header_information%%'
                    OR name = 'report_invoice_document_add_pesos'))
              OR arch_db::text LIKE '%%l10n_cr_document_id%%'
          )
        RETURNING id, name, key
    """, ())
    rows = cr.fetchall()
    if rows:
        _logger.info(
            'Pre-migration 5.0.19: deactivated %d broken view(s): %s',
            len(rows), [(r[1], r[2]) for r in rows],
        )
