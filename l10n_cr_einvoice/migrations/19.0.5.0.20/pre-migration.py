"""Fix invoice report templates and deactivate orphan views.

1. Deactivate orphan views from uninstalled invoice_weight module
   (peso_neto / peso_total fields cause KeyError on report rendering).
2. Re-parent l10n_cr_einvoice invoice report templates so they inherit
   from account_accountant.report_invoice_document (the ACTIVE base
   template in Odoo 19 Enterprise) instead of account.report_invoice_document
   (which is inactive).
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    # --- 1. Deactivate orphan views ---
    cr.execute("""
        UPDATE ir_ui_view SET active = false
        WHERE active = true
          AND (
              (type = 'qweb'
               AND key LIKE 'gen_key.%%'
               AND (arch_db::text LIKE '%%l10n_cr_header_information%%'
                    OR name = 'report_invoice_document_add_pesos'))
              OR arch_db::text LIKE '%%l10n_cr_document_id%%'
              OR (arch_db::text LIKE '%%peso_neto%%'
                  AND key LIKE 'gen_key.%%')
              OR (arch_db::text LIKE '%%peso_total%%'
                  AND key LIKE 'gen_key.%%'
                  AND name LIKE '%%weight%%')
          )
        RETURNING id, name, key
    """, ())
    rows = cr.fetchall()
    if rows:
        _logger.info(
            'Pre-migration 5.0.20: deactivated %d broken view(s): %s',
            len(rows), [(r[1], r[2]) for r in rows],
        )

    # --- 2. Re-parent invoice report templates ---
    # In Odoo 19 Enterprise, account_accountant replaces account's
    # report_invoice_document.  Our templates must inherit from the
    # ACTIVE one.
    cr.execute("""
        SELECT id FROM ir_ui_view
        WHERE name = 'report_invoice_document'
          AND key = 'account_accountant.report_invoice_document'
          AND active = true
        LIMIT 1
    """, ())
    row = cr.fetchone()
    if row:
        active_parent_id = row[0]
        cr.execute("""
            UPDATE ir_ui_view
            SET inherit_id = %s
            WHERE key LIKE 'l10n_cr_einvoice.report_invoice_fp%%'
              AND inherit_id != %s
            RETURNING id, name
        """, (active_parent_id, active_parent_id))
        fixed = cr.fetchall()
        if fixed:
            _logger.info(
                'Pre-migration 5.0.20: re-parented %d template(s) to '
                'account_accountant.report_invoice_document (id=%d): %s',
                len(fixed), active_parent_id,
                [r[1] for r in fixed],
            )
