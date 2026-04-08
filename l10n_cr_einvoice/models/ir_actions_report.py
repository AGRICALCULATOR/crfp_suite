from odoo import api, models


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    @api.model
    def _fp_assign_invoice_paperformat(self):
        """Assign custom CR invoice paper format to standard invoice report actions.

        Resolves reports by technical report_name to avoid external-id collisions
        across models/modules and remains idempotent during repeated upgrades.
        """
        paperformat = self.env.ref(
            "l10n_cr_einvoice.paperformat_a4_especial_no_header",
            raise_if_not_found=False,
        )
        if not paperformat:
            return False

        report_names = [
            "account.report_invoice",
            "account.report_invoice_with_payments",
        ]
        reports = self.search([("report_name", "in", report_names)])
        if reports:
            reports.write({"paperformat_id": paperformat.id})
        return True
