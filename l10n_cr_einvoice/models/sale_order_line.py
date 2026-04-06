from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    fp_net_weight = fields.Float(
        string="Peso neto",
        digits=(16, 3),
        copy=True,
        help="Peso neto total de la línea en kilogramos.",
    )
    fp_gross_weight = fields.Float(
        string="Peso bruto",
        digits=(16, 3),
        copy=True,
        help="Peso bruto total de la línea en kilogramos.",
    )

    @api.onchange("product_uom_qty", "product_id")
    def _onchange_fp_set_default_weights(self):
        for line in self:
            if line.display_type or not line.product_id:
                line.fp_net_weight = 0.0
                line.fp_gross_weight = 0.0
                continue
            default_weight = (line.product_uom_qty or 0.0) * (line.product_id.weight or 0.0)
            line.fp_net_weight = default_weight
            line.fp_gross_weight = default_weight

    def _prepare_invoice_line(self, **optional_values):
        values = super()._prepare_invoice_line(**optional_values)
        values.update(
            {
                "fp_net_weight": self.fp_net_weight,
                "fp_gross_weight": self.fp_gross_weight,
            }
        )
        return values
