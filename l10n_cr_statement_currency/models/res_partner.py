import base64
import json

from odoo import _, fields, models
from odoo.tools import float_is_zero
from odoo.tools.misc import formatLang


class ResPartner(models.Model):
    _inherit = "res.partner"

    statement_email = fields.Char(string="Correo para estados de cuenta")
    statement_email_cc = fields.Char(string="CC para estados de cuenta")

    # ------------------------------------------------------------------
    # Dynamic report (account_reports) entry point
    # ------------------------------------------------------------------
    def _get_statement_report(self):
        return self.env.ref("l10n_cr_statement_currency.statement_report")

    def _get_statement_report_options(self):
        self.ensure_one()
        report = self._get_statement_report()
        options = report.get_options(previous_options={})
        partner_id = str(self.id)
        options["partner_ids"] = [partner_id]
        options["selected_partner_ids"] = [partner_id]
        options["partner"] = [{"id": self.id, "name": self.display_name, "selected": True}]
        options["unfold_all"] = True
        return options

    def action_open_statement_report(self):
        self.ensure_one()
        report = self._get_statement_report()
        options = self._get_statement_report_options()
        return {
            "type": "ir.actions.client",
            "name": _("Estado de cuenta - %(partner)s") % {"partner": self.display_name},
            "tag": "account_report",
            "context": {
                "report_id": report.id,
                "options": json.dumps(options),
                "unfold_all": True,
                "active_model": "res.partner",
                "active_id": self.id,
                "default_partner_ids": [self.id],
                "statement_partner_ids": [self.id],
            },
        }

    # ------------------------------------------------------------------
    # Email configuration helpers
    # ------------------------------------------------------------------
    def _get_statement_target_emails(self):
        self.ensure_one()
        email_to = (self.statement_email or "").strip()
        email_cc = (self.statement_email_cc or "").strip()
        return {
            "email_to": email_to,
            "email_cc": email_cc,
        }

    def _get_followup_mail_recipients(self):
        """Extension hook for account_followup: prefer statement email fields."""
        self.ensure_one()
        recipients = super()._get_followup_mail_recipients() if hasattr(super(), "_get_followup_mail_recipients") else {}
        target = self._get_statement_target_emails()
        recipients.update({
            "email_to": target["email_to"],
            "email_cc": target["email_cc"],
        })
        return recipients

    def action_send_statement_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Enviar estado de cuenta"),
            "res_model": "statement.send.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_partner_id": self.id,
            },
        }

    def action_print_statement_pdf(self):
        self.ensure_one()
        return self.env.ref(
            "l10n_cr_statement_currency.action_partner_statement_pdf"
        ).report_action(self)

    # ------------------------------------------------------------------
    # PDF rendering (QWeb)
    # ------------------------------------------------------------------
    def _get_statement_pdf_filename(self):
        self.ensure_one()
        today = fields.Date.context_today(self)
        partner = (self.name or str(self.id)).replace("/", "-")
        return _("Estado_de_Cuenta_%(partner)s_%(date)s.pdf") % {
            "partner": partner,
            "date": today,
        }

    def _render_statement_report_pdf(self):
        self.ensure_one()
        report_xmlid = "l10n_cr_statement_currency.action_partner_statement_pdf"
        pdf_content, _content_type = (
            self.env["ir.actions.report"]
            .with_company(self.company_id)
            ._render_qweb_pdf(report_xmlid, res_ids=self.ids)
        )
        attachment = self.env["ir.attachment"].create(
            {
                "name": self._get_statement_pdf_filename(),
                "type": "binary",
                "datas": base64.b64encode(pdf_content),
                "mimetype": "application/pdf",
                "res_model": "res.partner",
                "res_id": self.id,
                "company_id": self.company_id.id,
            }
        )
        return attachment

    # ------------------------------------------------------------------
    # Data preparation for the QWeb PDF
    # ------------------------------------------------------------------
    _AGING_BUCKETS = ("current", "b1_30", "b31_60", "b61_90", "b90_plus")

    def _statement_format_amount(self, amount, currency):
        formatted = formatLang(self.env, amount or 0.0, currency_obj=currency)
        return formatted.replace("\u00a0", " ") if isinstance(formatted, str) else formatted

    def _prepare_statement_data(self, cutoff_date=None):
        self.ensure_one()
        cutoff_date = (
            cutoff_date
            or self.env.context.get("statement_cutoff_date")
            or fields.Date.context_today(self)
        )
        company = self.env.company

        invoices = self.env["account.move"].search(
            self._statement_invoice_domain(cutoff_date),
            order="invoice_date, id",
        )
        pending_lines = self.env["account.move.line"].search(
            self._statement_pending_payment_domain(cutoff_date),
            order="date, id",
        )

        by_currency = {}

        for move in invoices:
            currency = move.currency_id
            residual = move.amount_residual
            if float_is_zero(residual, precision_rounding=currency.rounding):
                continue
            sign = -1 if move.move_type == "out_refund" else 1
            original_amount = sign * move.amount_total
            residual_amount = sign * residual
            days_overdue = self._statement_days_overdue(move.invoice_date_due, cutoff_date)

            entry = self._statement_currency_entry(by_currency, currency)
            entry["invoices"].append(
                {
                    "number": move.fp_consecutive_number or move.name,
                    "invoice_date": move.invoice_date,
                    "invoice_date_due": move.invoice_date_due,
                    "days_overdue": days_overdue,
                    "original_amount": original_amount,
                    "residual_amount": residual_amount,
                    "original_formatted": self._statement_format_amount(original_amount, currency),
                    "residual_formatted": self._statement_format_amount(residual_amount, currency),
                }
            )
            entry["subtotal_original"] += original_amount
            entry["subtotal_balance"] += residual_amount
            bucket = self._statement_aging_bucket(days_overdue)
            entry["aging"][bucket] += residual_amount

        for line in pending_lines:
            currency = line.currency_id or line.company_currency_id
            payment_amount = -(line.amount_currency if line.currency_id else line.balance)
            residual_amount = -(line.amount_residual_currency if line.currency_id else line.amount_residual)
            if float_is_zero(residual_amount, precision_rounding=currency.rounding):
                continue

            entry = self._statement_currency_entry(by_currency, currency)
            entry["pending_payments"].append(
                {
                    "number": line.payment_id.name or line.move_id.name,
                    "payment_date": line.date,
                    "original_amount": payment_amount,
                    "residual_amount": residual_amount,
                    "original_formatted": self._statement_format_amount(payment_amount, currency),
                    "residual_formatted": self._statement_format_amount(residual_amount, currency),
                }
            )
            entry["pending_balance"] += residual_amount

        summary = []
        by_currency_list = []
        for entry in sorted(by_currency.values(), key=lambda e: e["currency_name"] or ""):
            currency = entry["currency"]
            net_balance = entry["subtotal_balance"] - entry["pending_balance"]
            entry["net_balance"] = net_balance
            entry["subtotal_original_formatted"] = self._statement_format_amount(entry["subtotal_original"], currency)
            entry["subtotal_balance_formatted"] = self._statement_format_amount(entry["subtotal_balance"], currency)
            entry["pending_balance_formatted"] = self._statement_format_amount(entry["pending_balance"], currency)
            entry["net_balance_formatted"] = self._statement_format_amount(net_balance, currency)
            entry["aging_formatted"] = {
                bucket: self._statement_format_amount(entry["aging"][bucket], currency)
                for bucket in self._AGING_BUCKETS
            }
            by_currency_list.append(entry)
            summary.append(
                {
                    "currency": currency,
                    "currency_name": entry["currency_name"],
                    "invoices_balance": entry["subtotal_balance"],
                    "pending_balance": entry["pending_balance"],
                    "net_balance": net_balance,
                    "invoices_balance_formatted": entry["subtotal_balance_formatted"],
                    "pending_balance_formatted": entry["pending_balance_formatted"],
                    "net_balance_formatted": entry["net_balance_formatted"],
                }
            )

        return {
            "company": company,
            "cutoff_date": cutoff_date,
            "by_currency": by_currency_list,
            "currency_summary": summary,
        }

    def _statement_currency_entry(self, container, currency):
        if currency.id in container:
            return container[currency.id]
        entry = {
            "currency": currency,
            "currency_name": currency.name,
            "invoices": [],
            "pending_payments": [],
            "subtotal_original": 0.0,
            "subtotal_balance": 0.0,
            "pending_balance": 0.0,
            "net_balance": 0.0,
            "aging": {bucket: 0.0 for bucket in self._AGING_BUCKETS},
        }
        container[currency.id] = entry
        return entry

    def _statement_invoice_domain(self, cutoff_date):
        return [
            ("partner_id", "=", self.id),
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("state", "=", "posted"),
            ("amount_residual", "!=", 0.0),
            ("company_id", "in", self.env.companies.ids),
            ("invoice_date", "<=", cutoff_date),
        ]

    def _statement_pending_payment_domain(self, cutoff_date):
        return [
            ("partner_id", "=", self.id),
            ("account_id.account_type", "=", "asset_receivable"),
            ("parent_state", "=", "posted"),
            ("payment_id", "!=", False),
            ("reconciled", "=", False),
            ("amount_residual", "<", 0.0),
            ("company_id", "in", self.env.companies.ids),
            ("date", "<=", cutoff_date),
        ]

    def _statement_days_overdue(self, due_date, reference_date):
        if not due_date:
            return 0
        delta = (reference_date - due_date).days
        return delta if delta > 0 else 0

    def _statement_aging_bucket(self, days_overdue):
        if days_overdue <= 0:
            return "current"
        if days_overdue <= 30:
            return "b1_30"
        if days_overdue <= 60:
            return "b31_60"
        if days_overdue <= 90:
            return "b61_90"
        return "b90_plus"
