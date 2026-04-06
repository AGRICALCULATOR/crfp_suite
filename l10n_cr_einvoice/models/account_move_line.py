from odoo import api, fields, models


FP_DISCOUNT_CODE_SELECTION = [
    ("01", "01 - Descuento por regalía"),
    ("02", "02 - Descuento por regalía o bonificaciones IVA cobrado al cliente"),
    ("03", "03 - Descuento por bonificación"),
    ("04", "04 - Descuento por volumen"),
    ("05", "05 - Descuento por temporada (estacional)"),
    ("06", "06 - Descuento promocional"),
    ("07", "07 - Descuento comercial"),
    ("08", "08 - Descuento por frecuencia"),
    ("09", "09 - Descuento sostenido"),
    ("99", "99 - Otros descuentos"),
]


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    exclude_from_invoice_tab = fields.Boolean(
        string="Exclude From Invoice Tab",
        default=False,
        help="Compatibility field for invoice report templates expecting this flag.",
    )
    fp_is_other_charge_line = fields.Boolean(
        string="Línea contable de otros cargos FE",
        default=False,
        copy=True,
        help="Marca técnica para identificar líneas automáticas de otros cargos FE.",
    )
    fp_other_charge_id = fields.Many2one(
        "account.move.other.charge",
        string="Origen otro cargo FE",
        copy=True,
        readonly=True,
        help="Referencia técnica al registro de otros cargos que originó la línea contable.",
    )
    fp_discount_code = fields.Selection(
        FP_DISCOUNT_CODE_SELECTION,
        string="Tipo de descuento FE",
        default="07",
        copy=True,
        help="Código de descuento enviado en el nodo LineaDetalle/Descuento/CodigoDescuento.",
    )
    fp_discount_nature = fields.Char(
        string="Naturaleza del descuento FE",
        copy=True,
        help="Descripción libre enviada en LineaDetalle/Descuento/NaturalezaDescuento.",
    )
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

    @api.onchange("quantity", "product_id")
    def _onchange_fp_set_default_weights(self):
        for line in self:
            line._fp_apply_default_weights()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._fp_prepare_weight_vals(vals)
        return super().create(vals_list)

    def _fp_prepare_weight_vals(self, vals):
        if vals.get("display_type"):
            vals.setdefault("fp_net_weight", 0.0)
            vals.setdefault("fp_gross_weight", 0.0)
            return
        if vals.get("fp_net_weight") is not None and vals.get("fp_gross_weight") is not None:
            return
        product = self.env["product.product"].browse(vals.get("product_id")) if vals.get("product_id") else False
        quantity = vals.get("quantity", 0.0)
        default_weight = (product.weight or 0.0) * quantity if product else 0.0
        vals.setdefault("fp_net_weight", default_weight)
        vals.setdefault("fp_gross_weight", default_weight)

    def _fp_apply_default_weights(self):
        for line in self:
            if line.display_type or not line.product_id:
                line.fp_net_weight = 0.0
                line.fp_gross_weight = 0.0
                continue
            default_weight = (line.quantity or 0.0) * (line.product_id.weight or 0.0)
            line.fp_net_weight = default_weight
            line.fp_gross_weight = default_weight
