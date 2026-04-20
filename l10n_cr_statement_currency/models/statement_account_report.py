from odoo import _, fields, models
from odoo.exceptions import UserError


class AccountReport(models.Model):
    _inherit = "account.report"

    def _postprocess_chatter_for_annotations(self, lines):
        """Make report lines compatible with Odoo's chatter annotation postprocessing.

        Some Odoo 19 builds subscript ``line['move_id'][0]`` without checking if
        the value is truthy or even a sequence. Custom reports (especially section
        headers/subtotals and synthetic ids) may end up with ``move_id=False``.
        """
        self._sanitize_move_id(lines)
        return super()._postprocess_chatter_for_annotations(lines)

    def _sanitize_move_id(self, lines):
        for line in self._walk_line_dicts(lines):
            if "move_id" not in line:
                continue

            value = line.get("move_id")

            if isinstance(value, (list, tuple)):
                if not value:
                    line["move_id"] = (False, "")
                    continue
                move_id = value[0]
                display = value[1] if len(value) > 1 else (line.get("name") or "")
                line["move_id"] = (move_id or False, display or "")
                continue

            if isinstance(value, int):
                line["move_id"] = (value, line.get("name") or "")
                continue

            record_id = getattr(value, "id", False) if value else False
            line["move_id"] = (record_id or False, "")

    def _walk_line_dicts(self, obj):
        """Yield every dict that represents a report line, including nested structures."""
        if isinstance(obj, dict):
            yield obj
            for key in ("children", "lines", "unfolded_lines"):
                nested = obj.get(key)
                if isinstance(nested, list):
                    for item in nested:
                        yield from self._walk_line_dicts(item)
            return

        if isinstance(obj, (list, tuple)):
            for item in obj:
                yield from self._walk_line_dicts(item)

    # ------------------------------------------------------------------
    # PDF export override: route our statement report to the QWeb action
    # so both the toolbar PDF button and the partner form produce the
    # same polished statement.
    # ------------------------------------------------------------------
    def export_to_pdf(self, options):
        statement_report = self.env.ref(
            "l10n_cr_statement_currency.statement_report", raise_if_not_found=False
        )
        if statement_report and self.id == statement_report.id:
            return self._export_statement_to_custom_pdf(options)
        return super().export_to_pdf(options)

    def _export_statement_to_custom_pdf(self, options):
        self.ensure_one()
        partners = self._statement_partners_from_options(options)
        if not partners:
            raise UserError(
                _("No hay clientes con saldo pendiente para los filtros indicados.")
            )

        cutoff_date = self._statement_cutoff_from_options(options)
        report_xmlid = "l10n_cr_statement_currency.action_partner_statement_pdf"

        pdf_content, _dummy_type = (
            self.env["ir.actions.report"]
            .with_context(statement_cutoff_date=cutoff_date)
            ._render_qweb_pdf(report_xmlid, res_ids=partners.ids)
        )

        if len(partners) == 1:
            partner_name = (partners.name or str(partners.id)).replace("/", "-")
            filename = _("Estado de Cuenta - %(partner)s - %(date)s.pdf") % {
                "partner": partner_name,
                "date": cutoff_date,
            }
        else:
            filename = _("Estados de Cuenta - %(date)s.pdf") % {"date": cutoff_date}

        return {
            "file_name": filename,
            "file_content": pdf_content,
            "fileType": "pdf",
        }

    def _statement_partners_from_options(self, options):
        explicit = []
        for pid in options.get("partner_ids") or []:
            try:
                explicit.append(int(pid))
            except (TypeError, ValueError):
                continue
        if explicit:
            return self.env["res.partner"].browse(explicit).exists()

        cutoff = self._statement_cutoff_from_options(options)
        domain = [
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("state", "=", "posted"),
            ("amount_residual", "!=", 0.0),
            ("company_id", "in", self.env.companies.ids),
            ("invoice_date", "<=", cutoff),
        ]
        selected_journal_ids = [
            journal.get("id")
            for journal in (options.get("journals") or [])
            if journal.get("id") and journal.get("selected")
        ]
        if selected_journal_ids:
            domain.append(("journal_id", "in", selected_journal_ids))

        moves = self.env["account.move"].search(domain)
        return moves.mapped("partner_id").sorted(lambda p: (p.name or "").lower())

    def _statement_cutoff_from_options(self, options):
        raw_date_to = (options.get("date") or {}).get("date_to")
        if raw_date_to:
            try:
                return fields.Date.to_date(raw_date_to)
            except (ValueError, TypeError):
                pass
        return fields.Date.context_today(self)
