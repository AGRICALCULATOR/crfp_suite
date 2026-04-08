import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def _register_hook(self):
        """Run on every server start: deactivate broken l10n_cr views for Odoo 19.

        The standard l10n_cr module (Costa Rica localization) has views that
        reference elements/fields removed in Odoo 19:
        - 'l10n_cr_header_information' / 'no_shipping' in QWeb report templates
        - 'l10n_cr_document_id' field in list/form views

        These cause QWebError or validation errors and block invoice rendering.
        This hook runs on every registry load — no manual upgrade needed.
        Only targets auto-generated views (gen_key.*) to avoid touching our own.
        """
        super()._register_hook()
        cr = self.env.cr

        # 1. Broken QWeb report templates (gen_key.* views from l10n_cr)
        cr.execute("""
            UPDATE ir_ui_view SET active = false
            WHERE active = true
              AND type = 'qweb'
              AND (arch_db LIKE '%%l10n_cr_header_information%%'
                   OR (arch_db LIKE '%%no_shipping%%'
                       AND key LIKE 'gen_key.%%'))
            RETURNING id, key
        """)
        qweb_rows = cr.fetchall()

        # 2. Broken form/list views referencing l10n_cr_document_id (field removed in Odoo 19)
        cr.execute("""
            UPDATE ir_ui_view SET active = false
            WHERE active = true
              AND arch_db LIKE '%%l10n_cr_document_id%%'
            RETURNING id, key
        """)
        form_rows = cr.fetchall()

        all_rows = qweb_rows + form_rows
        if all_rows:
            _logger.info(
                'Deactivated %d broken l10n_cr view(s): %s',
                len(all_rows), [r[1] for r in all_rows],
            )

    @api.model
    def _fp_assign_invoice_paperformat(self):
        """Assign custom CR invoice paper format to standard invoice report actions.

        Resolves reports by technical `report_name` to avoid external-id collisions
        across models/modules and remains idempotent during repeated upgrades.
        """
        paperformat = self.env.ref("l10n_cr_einvoice.paperformat_a4_especial_no_header", raise_if_not_found=False)
        if not paperformat:
            return False

        report_names = ["account.report_invoice", "account.report_invoice_with_payments"]
        reports = self.search([("report_name", "in", report_names)])
        if reports:
            reports.write({"paperformat_id": paperformat.id})
        return True
