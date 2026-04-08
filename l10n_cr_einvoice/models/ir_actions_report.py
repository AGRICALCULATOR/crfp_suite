import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def _register_hook(self):
        """Run on every server start: deactivate broken QWeb views for Odoo 19.

        Views from l10n_cr or auto-generated (gen_key.*) that reference
        elements like 'l10n_cr_header_information' or 'no_shipping' cause
        QWebError because those elements don't exist in Odoo 19's invoice
        template. This runs on registry load — no manual upgrade needed.
        """
        super()._register_hook()
        cr = self.env.cr
        cr.execute("""
            UPDATE ir_ui_view SET active = false
            WHERE active = true
              AND type = 'qweb'
              AND (arch_db LIKE '%%l10n_cr_header_information%%'
                   OR (arch_db LIKE '%%no_shipping%%'
                       AND key LIKE 'gen_key.%%'))
            RETURNING id, key
        """)
        rows = cr.fetchall()
        if rows:
            _logger.info(
                'Deactivated %d broken QWeb view(s): %s',
                len(rows), [r[1] for r in rows],
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
