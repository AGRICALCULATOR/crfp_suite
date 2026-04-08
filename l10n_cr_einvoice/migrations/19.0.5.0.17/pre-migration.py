"""Deactivate orphan views that break invoice PDF rendering in Odoo 19.

Previous migrations (5.0.15, 5.0.16) used %% in LIKE patterns but called
cursor.execute() without a params tuple, so psycopg2 sent literal '%%' to
PostgreSQL and matched nothing.  This version uses single % (correct when
there is no params argument).

Target views (all orphans created via UI/RPC, key = gen_key.*):
  - report_invoice_document_receptor  (xpath l10n_cr_header_information)
  - report_invoice_document_add_pesos (duplicate peso columns)
  - Any view referencing removed field l10n_cr_document_id
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("""
        UPDATE ir_ui_view SET active = false
        WHERE active = true
          AND (
              (type = 'qweb'
               AND key LIKE 'gen_key.%'
               AND (arch_db::text LIKE '%l10n_cr_header_information%'
                    OR name = 'report_invoice_document_add_pesos'))
              OR arch_db::text LIKE '%l10n_cr_document_id%'
          )
        RETURNING id, name, key
    """)
    rows = cr.fetchall()
    if rows:
        _logger.info(
            'Pre-migration 5.0.17: deactivated %d broken view(s): %s',
            len(rows), [(r[1], r[2]) for r in rows],
        )
