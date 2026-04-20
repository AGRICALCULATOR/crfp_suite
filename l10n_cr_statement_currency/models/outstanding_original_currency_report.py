from collections import defaultdict

from odoo import _, fields, models
from odoo.tools.misc import formatLang
from odoo.tools import float_is_zero


class OutstandingOriginalCurrencyReportHandler(models.AbstractModel):
    _name = "account.outstanding.original.currency.report.handler"
    _inherit = "account.report.custom.handler"
    _description = "Outstanding Receivable in Original Currency Report Handler"
    _COLUMN_EXPRESSIONS = ("fecha", "fecha_vencimiento", "dias_vencidos", "importe_original", "saldo")

    def _custom_options_initializer(self, report, options, previous_options=None):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        self._apply_context_partner_filter(options)
        # Force everything unfolded on first open. The super() initializer sets
        # unfold_all=False by default for filter_unfold_all reports, so a plain
        # setdefault isn't enough — we have to overwrite. Preserve the user's
        # explicit toggle if they already customised this session's options.
        if previous_options and "unfold_all" in previous_options:
            options["unfold_all"] = previous_options["unfold_all"]
        else:
            options["unfold_all"] = True
        self._sync_column_labels(report, options)

    def _sync_column_labels(self, report, options):
        """Keep Odoo's header metadata intact and only fill visible labels."""
        ordered_columns = report.column_ids.sorted("sequence")
        if not ordered_columns:
            return

        labels_by_expression = {
            column.expression_label: column.name
            for column in ordered_columns
            if column.expression_label
        }
        ordered_labels = [column.name for column in ordered_columns]

        for index, column in enumerate(options.get("columns", [])):
            label = labels_by_expression.get(column.get("expression_label"))
            if not label and index < len(ordered_labels):
                label = ordered_labels[index]
            if label:
                column["name"] = label

        column_headers = options.get("column_headers") or []
        for row in column_headers:
            for cell in row:
                label = labels_by_expression.get(cell.get("expression_label"))
                if label:
                    cell["name"] = label

        # Some Odoo 19 builds provide leaf header cells without expression_label.
        # The leaf row is the last header row, but it can include fewer cells than
        # report columns when column groups are active.
        if not column_headers:
            return

        leaf_row = column_headers[-1]
        labels_to_apply = ordered_labels[-len(leaf_row) :]
        start_index = len(leaf_row) - len(labels_to_apply)

        for index, label in enumerate(labels_to_apply):
            header_index = start_index + index
            if not leaf_row[header_index].get("name"):
                leaf_row[header_index]["name"] = label

    def _apply_context_partner_filter(self, options):
        """Apply the partner scope from context; never wipe what the user chose.

        Wiping options[partner_ids] when context lacks a partner was breaking
        PDF and XLSX exports in Odoo 19 Cloudpepper: the export RPC strips
        our partner-specific context keys, so the handler saw "no partner"
        and dropped the filter the user had on screen. Always honour the
        filter already present in options.

        Trade-off: a partner filter set from a previous partner-scoped
        session is stored in account_reports' previous_options, so the
        menu entry may still reload that old filter. The user can clear it
        from the filter chip in the UI when they want a clean global view.
        """
        context = self.env.context
        context_partner_ids = context.get("statement_partner_ids") or context.get("default_partner_ids") or []
        if isinstance(context_partner_ids, int):
            context_partner_ids = [context_partner_ids]

        if not context_partner_ids and context.get("active_model") == "res.partner" and context.get("active_id"):
            context_partner_ids = [context["active_id"]]

        partner_ids = [int(pid) for pid in context_partner_ids if pid]
        if not partner_ids:
            return

        partners = self.env["res.partner"].browse(partner_ids)
        options["partner_ids"] = partner_ids
        # Keep the partner filter for querying, but avoid exposing internal IDs in the PDF header.
        options["selected_partner_ids"] = []
        options["partner"] = [{"id": partner.id, "name": partner.display_name, "selected": True} for partner in partners]

    def _dynamic_lines_generator(self, report, options, all_column_groups_expression_totals, warnings=None):
        grouped_results = self._get_grouped_moves(options)
        lines = []

        unfolded_lines = set(options.get("unfolded_lines", []))
        unfold_all = options.get("unfold_all")

        for partner_key in sorted(grouped_results.keys(), key=lambda key: (key[1] or "").lower()):
            partner_id, partner_name = partner_key
            partner_payload = grouped_results[partner_key]
            partner_line_id = report._get_generic_line_id("res.partner", partner_id, markup="partner")
            partner_is_unfolded = unfold_all or partner_line_id in unfolded_lines

            lines.append(
                {
                    "id": partner_line_id,
                    "name": partner_name or _("No Partner"),
                    "level": 1,
                    "unfoldable": True,
                    "unfolded": bool(partner_is_unfolded),
                    "class": "o_statement_original_currency_partner",
                    "columns": self._empty_columns(),
                }
            )

            if not partner_is_unfolded:
                continue

            for currency_id, currency_data in sorted(
                partner_payload.items(), key=lambda item: (item[1]["currency_name"] or "")
            ):
                currency = self.env["res.currency"].browse(currency_id)
                currency_line_id = report._get_generic_line_id(
                    "res.currency", currency_id, parent_line_id=partner_line_id, markup="currency"
                )
                currency_is_unfolded = unfold_all or currency_line_id in unfolded_lines

                lines.append(
                    {
                        "id": currency_line_id,
                        "parent_id": partner_line_id,
                        "name": currency_data["currency_name"],
                        "level": 2,
                        "unfoldable": True,
                        "unfolded": bool(currency_is_unfolded),
                        "class": "o_statement_original_currency_currency",
                        "columns": self._empty_columns(),
                    }
                )

                if not currency_is_unfolded:
                    continue

                for move in currency_data["moves"]:
                    lines.append(
                        {
                            "id": report._get_generic_line_id("account.move", move["id"], parent_line_id=currency_line_id),
                            "parent_id": currency_line_id,
                            "name": move["display_number"],
                            "level": 3,
                            "caret_options": "account.move",
                            "move_id": (move["id"], move["display_number"]),
                            "class": "o_statement_original_currency_detail",
                            "columns": [
                                {
                                    "name": self._fmt_date(move["invoice_date"]),
                                    "expression_label": "fecha",
                                },
                                {
                                    "name": self._fmt_date(move["invoice_date_due"]),
                                    "expression_label": "fecha_vencimiento",
                                },
                                self._days_col(move["days_overdue"]),
                                {
                                    "expression_label": "importe_original",
                                    **self._monetary_col(report, move["original_amount"], currency),
                                },
                                {
                                    "expression_label": "saldo",
                                    **self._monetary_col(report, move["residual_amount"], currency),
                                },
                            ],
                        }
                    )

                lines.append(
                    {
                        "id": report._get_generic_line_id("res.currency", currency_id, parent_line_id=currency_line_id, markup="subtotal"),
                        "parent_id": currency_line_id,
                        "name": _("Subtotal"),
                        "level": 3,
                        "class": "o_statement_original_currency_subtotal",
                        "columns": [
                            {"name": "", "expression_label": "fecha"},
                            {"name": "", "expression_label": "fecha_vencimiento"},
                            {"name": "", "expression_label": "dias_vencidos"},
                            {
                                "expression_label": "importe_original",
                                **self._monetary_col(report, currency_data["subtotal_original"], currency),
                            },
                            {
                                "expression_label": "saldo",
                                **self._monetary_col(report, currency_data["subtotal_residual"], currency),
                            },
                        ],
                    }
                )

        self._append_pending_payments_section(report, options, lines, unfolded_lines, unfold_all)
        return [(0, line) for line in lines]

    def _append_pending_payments_section(self, report, options, lines, unfolded_lines, unfold_all):
        grouped_pending_payments = self._get_grouped_pending_payments(options)
        if not grouped_pending_payments:
            return

        section_line_id = report._get_generic_line_id("account.report", report.id, markup="pending_payments_section")
        lines.append(
            {
                "id": section_line_id,
                "name": _("Pending payments to reconcile"),
                "level": 1,
                "class": "o_statement_original_currency_section",
                "columns": self._empty_columns(),
            }
        )

        for partner_key in sorted(grouped_pending_payments.keys(), key=lambda key: (key[1] or "").lower()):
            partner_id, partner_name = partner_key
            partner_payload = grouped_pending_payments[partner_key]
            partner_line_id = report._get_generic_line_id(
                "res.partner", partner_id, parent_line_id=section_line_id, markup="pending_payment_partner"
            )
            partner_is_unfolded = unfold_all or partner_line_id in unfolded_lines

            lines.append(
                {
                    "id": partner_line_id,
                    "parent_id": section_line_id,
                    "name": partner_name or _("No Partner"),
                    "level": 2,
                    "unfoldable": True,
                    "unfolded": bool(partner_is_unfolded),
                    "class": "o_statement_original_currency_partner",
                    "columns": self._empty_columns(),
                }
            )

            if not partner_is_unfolded:
                continue

            for currency_id, currency_data in sorted(
                partner_payload.items(), key=lambda item: (item[1]["currency_name"] or "")
            ):
                currency = self.env["res.currency"].browse(currency_id)
                currency_line_id = report._get_generic_line_id(
                    "res.currency", currency_id, parent_line_id=partner_line_id, markup="pending_payment_currency"
                )
                currency_is_unfolded = unfold_all or currency_line_id in unfolded_lines

                lines.append(
                    {
                        "id": currency_line_id,
                        "parent_id": partner_line_id,
                        "name": currency_data["currency_name"],
                        "level": 3,
                        "unfoldable": True,
                        "unfolded": bool(currency_is_unfolded),
                        "class": "o_statement_original_currency_currency",
                        "columns": self._empty_columns(),
                    }
                )

                if not currency_is_unfolded:
                    continue

                for payment in currency_data["payments"]:
                    lines.append(
                        {
                            "id": report._get_generic_line_id("account.move", payment["move_id"], parent_line_id=currency_line_id),
                            "parent_id": currency_line_id,
                            "name": payment["display_number"],
                            "level": 4,
                            "caret_options": "account.move",
                            "move_id": (payment["move_id"], payment["display_number"]),
                            "class": "o_statement_original_currency_detail",
                            "columns": [
                                {
                                    "name": self._fmt_date(payment["payment_date"]),
                                    "expression_label": "fecha",
                                },
                                {"name": "", "expression_label": "fecha_vencimiento"},
                                {"name": "", "expression_label": "dias_vencidos"},
                                {
                                    "expression_label": "importe_original",
                                    **self._monetary_col(report, payment["payment_amount"], currency),
                                },
                                {
                                    "expression_label": "saldo",
                                    **self._monetary_col(report, payment["residual_amount"], currency),
                                },
                            ],
                        }
                    )

                lines.append(
                    {
                        "id": report._get_generic_line_id(
                            "res.currency", currency_id, parent_line_id=currency_line_id, markup="pending_payment_subtotal"
                        ),
                        "parent_id": currency_line_id,
                        "name": _("Subtotal"),
                        "level": 4,
                        "class": "o_statement_original_currency_subtotal",
                        "columns": [
                            {"name": "", "expression_label": "fecha"},
                            {"name": "", "expression_label": "fecha_vencimiento"},
                            {"name": "", "expression_label": "dias_vencidos"},
                            {
                                "expression_label": "importe_original",
                                **self._monetary_col(report, currency_data["subtotal_original"], currency),
                            },
                            {
                                "expression_label": "saldo",
                                **self._monetary_col(report, currency_data["subtotal_residual"], currency),
                            },
                        ],
                    }
                )

    def _empty_columns(self):
        return [{"name": "", "expression_label": expression} for expression in self._COLUMN_EXPRESSIONS]

    def _report_custom_engine_outstanding_original_currency(self, *args, **kwargs):
        """Placeholder to expose editable expression rows in report configuration."""
        return {}

    def _get_grouped_moves(self, options):
        moves = self.env["account.move"].search(
            self._get_moves_domain(options),
            order="partner_id, currency_id, invoice_date, id",
        )

        reference_date = self._get_reference_date(options)
        partner_currency_map = defaultdict(dict)
        for move in moves:
            currency = move.currency_id
            residual_amount = move.amount_residual
            if float_is_zero(residual_amount, precision_rounding=currency.rounding):
                continue

            partner_key = (move.partner_id.id, move.partner_id.name or _("No Partner"))
            currency_id = currency.id
            if currency_id not in partner_currency_map[partner_key]:
                partner_currency_map[partner_key][currency_id] = {
                    "currency_name": currency.name,
                    "subtotal_original": 0.0,
                    "subtotal_residual": 0.0,
                    "moves": [],
                }

            sign = -1 if move.move_type == "out_refund" else 1
            original_amount = sign * move.amount_total
            residual_amount = sign * residual_amount

            partner_currency_map[partner_key][currency_id]["subtotal_original"] += original_amount
            partner_currency_map[partner_key][currency_id]["subtotal_residual"] += residual_amount
            partner_currency_map[partner_key][currency_id]["moves"].append(
                {
                    "id": move.id,
                    "invoice_date": move.invoice_date,
                    "invoice_date_due": move.invoice_date_due,
                    "display_number": move.fp_consecutive_number or move.name,
                    "original_amount": original_amount,
                    "residual_amount": residual_amount,
                    "days_overdue": self._compute_days_overdue(move.invoice_date_due, reference_date),
                }
            )

        for partner_data in partner_currency_map.values():
            for currency_payload in partner_data.values():
                currency_payload["moves"].sort(
                    key=lambda move: (move["invoice_date"] or fields.Date.to_date("1900-01-01"), move["id"])
                )

        return partner_currency_map

    def _get_reference_date(self, options):
        today = fields.Date.context_today(self)
        date_options = options.get("date") or {}
        raw_date_to = date_options.get("date_to")
        if raw_date_to:
            try:
                parsed = fields.Date.to_date(raw_date_to)
                return min(parsed, today)
            except (ValueError, TypeError):
                pass
        return today

    def _compute_days_overdue(self, due_date, reference_date):
        if not due_date:
            return 0
        delta = (reference_date - due_date).days
        return delta if delta > 0 else 0

    def _days_col(self, value):
        return {
            "name": str(value) if value else "",
            "no_format": value or 0,
            "expression_label": "dias_vencidos",
            "figure_type": "integer",
            "class": "number",
        }

    def _get_moves_domain(self, options):
        # Outstanding balance is a point-in-time snapshot: include every
        # posted invoice/refund with residual up to the cutoff date, ignoring
        # any lower date bound the UI might provide.
        domain = [
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("state", "=", "posted"),
            ("amount_residual", "!=", 0.0),
            ("company_id", "in", self.env.companies.ids),
        ]

        date_to = (options.get("date") or {}).get("date_to")
        if date_to:
            domain.append(("invoice_date", "<=", date_to))

        selected_journal_ids = self._get_selected_journal_ids(options)
        if selected_journal_ids:
            domain.append(("journal_id", "in", selected_journal_ids))

        partner_ids = self._extract_partner_ids(options)
        if partner_ids:
            domain.append(("partner_id", "in", partner_ids))
        return domain

    def _get_grouped_pending_payments(self, options):
        pending_lines = self.env["account.move.line"].search(
            self._get_pending_payment_lines_domain(options),
            order="partner_id, currency_id, date, id",
        )

        partner_currency_map = defaultdict(dict)
        for line in pending_lines:
            currency = line.currency_id or line.company_currency_id
            residual_amount = self._get_receivable_residual_amount(line, currency)
            if float_is_zero(residual_amount, precision_rounding=currency.rounding):
                continue

            payment_amount = self._get_receivable_original_amount(line, currency)
            if float_is_zero(payment_amount, precision_rounding=currency.rounding):
                continue

            partner_key = (line.partner_id.id, line.partner_id.name or _("No Partner"))
            currency_id = currency.id
            if currency_id not in partner_currency_map[partner_key]:
                partner_currency_map[partner_key][currency_id] = {
                    "currency_name": currency.name,
                    "subtotal_original": 0.0,
                    "subtotal_residual": 0.0,
                    "payments": [],
                }

            partner_currency_map[partner_key][currency_id]["subtotal_original"] += payment_amount
            partner_currency_map[partner_key][currency_id]["subtotal_residual"] += residual_amount
            partner_currency_map[partner_key][currency_id]["payments"].append(
                {
                    "line_id": line.id,
                    "move_id": line.move_id.id,
                    "payment_date": line.date,
                    "display_number": line.payment_id.name or line.move_id.name,
                    "payment_amount": payment_amount,
                    "residual_amount": residual_amount,
                }
            )

        return partner_currency_map

    def _get_pending_payment_lines_domain(self, options):
        domain = [
            ("account_id.account_type", "=", "asset_receivable"),
            ("parent_state", "=", "posted"),
            ("payment_id", "!=", False),
            ("reconciled", "=", False),
            ("partner_id", "!=", False),
            ("company_id", "in", self.env.companies.ids),
            ("amount_residual", "<", 0.0),
        ]

        date_to = (options.get("date") or {}).get("date_to")
        if date_to:
            domain.append(("date", "<=", date_to))

        selected_journal_ids = self._get_selected_journal_ids(options)
        if selected_journal_ids:
            domain.append(("journal_id", "in", selected_journal_ids))

        partner_ids = self._extract_partner_ids(options)
        if partner_ids:
            domain.append(("partner_id", "in", partner_ids))
        return domain

    def _get_selected_journal_ids(self, options):
        return [
            journal.get("id")
            for journal in (options.get("journals") or [])
            if journal.get("id") and journal.get("selected")
        ]

    def _get_receivable_original_amount(self, line, currency):
        if line.currency_id:
            return -line.amount_currency
        return -line.balance

    def _get_receivable_residual_amount(self, line, currency):
        if line.currency_id:
            return -line.amount_residual_currency
        return -line.amount_residual

    def _extract_partner_ids(self, options):
        partner_ids = options.get("partner_ids") or []
        if isinstance(partner_ids, str):
            parsed_partner_ids = []
            for partner_id in partner_ids.split(","):
                partner_id = (partner_id or "").strip()
                if not partner_id:
                    continue
                if partner_id.isdigit():
                    parsed_partner_ids.append(int(partner_id))
            return parsed_partner_ids

        result = []
        for partner_id in partner_ids:
            if isinstance(partner_id, (list, tuple)):
                partner_id = partner_id[0]
            if partner_id:
                result.append(int(partner_id))

        if result:
            return result

        partner_filter_values = options.get("partner")
        if isinstance(partner_filter_values, dict):
            partner_filter_values = [partner_filter_values]
        elif not isinstance(partner_filter_values, (list, tuple)):
            partner_filter_values = []
        filter_partner_ids = [
            int(partner.get("id"))
            for partner in partner_filter_values
            if isinstance(partner, dict) and partner.get("id") and partner.get("selected")
        ]
        if filter_partner_ids:
            return filter_partner_ids

        selected_partner_ids = options.get("selected_partner_ids") or []
        return [int(pid) for pid in selected_partner_ids if pid]

    def _monetary_col(self, report, amount, currency):
        amount = currency.round(amount or 0.0)
        return {
            "name": formatLang(self.env, amount, currency_obj=currency),
            "no_format": amount,
            "figure_type": "monetary",
            "currency_id": currency.id,
            "class": "number",
        }

    def _fmt_date(self, date_value):
        return date_value.strftime("%d/%m/%Y") if date_value else ""
