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
        options.setdefault("unfold_all", False)
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
