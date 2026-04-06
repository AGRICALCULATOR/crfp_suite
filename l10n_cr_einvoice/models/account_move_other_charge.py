from odoo import _, api, fields, models
from odoo.exceptions import ValidationError



class AccountMoveOtherCharge(models.Model):
    _name = "account.move.other.charge"
    _description = "Otros Cargos FE v4.4"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    move_id = fields.Many2one(
        "account.move",
        string="Factura",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(related="move_id.company_id", store=True, readonly=True, index=True)
    currency_id = fields.Many2one(related="move_id.currency_id", store=True, readonly=True)
    calculation_type = fields.Selection(
        [
            ("amount", "Monto"),
            ("percentage", "Porcentaje"),
        ],
        string="Cálculo",
        required=True,
        default="amount",
    )
    document_type = fields.Selection(
        [
            ("01", "01 - Contribución parafiscal"),
            ("02", "02 - Timbre de la Cruz Roja"),
            ("03", "03 - Timbre de Benemérito Cuerpo de Bomberos de Costa Rica"),
            ("04", "04 - Cobro de un tercero"),
            ("05", "05 - Costos de Exportación"),
            ("06", "06 - Impuesto de servicio 10%"),
            ("07", "07 - Timbre de Colegios Profesionales"),
            ("08", "08 - Depósitos de Garantía"),
            ("09", "09 - Multas o Penalizaciones"),
            ("10", "10 - Intereses Moratorios"),
            ("99", "99 - Otros Cargos"),
        ],
        string="Tipo documento",
        required=True,
        default="99",
    )
    account_id = fields.Many2one(
        "account.account",
        string="Cuenta contable",
        domain="[('company_ids', 'parent_of', company_id)]",
        required=False,
    )
    document_type_other = fields.Char(
        string="Tipo documento OTROS",
        help="Descripción obligatoria cuando Tipo documento = 99 (TipoDocumentoOTROS en XML FE 4.4).",
    )
    third_party_id = fields.Many2one(
        "res.partner",
        string="Tercero",
        help="Tercero relacionado al cargo para poblar IdentificacionTercero y NombreTercero en XML cuando aplique.",
    )
    detail = fields.Char(string="Detalle", required=True)
    percentage = fields.Float(string="Porcentaje", digits=(16, 5))
    untaxed_base_amount = fields.Monetary(
        string="Base sin otros cargos",
        currency_field="currency_id",
        readonly=True,
        copy=False,
        help=(
            "Base imponible congelada al momento de configurar el otro cargo FE. "
            "Para porcentaje, evita variaciones por recomputos transitorios del formulario."
        ),
    )
    amount_manual = fields.Monetary(string="Monto manual", currency_field="currency_id")
    amount = fields.Monetary(
        string="Monto cargo",
        currency_field="currency_id",
        compute="_compute_amount",
        store=True,
    )
    fp_total_other_charge = fields.Monetary(
        string="Monto cargo FE",
        currency_field="currency_id",
        related="amount",
        store=True,
        readonly=True,
        help="Alias técnico para exponer exactamente el mismo importe de 'amount' sin cálculo adicional.",
    )

    @api.depends(
        "calculation_type",
        "percentage",
        "amount_manual",
        "move_id.currency_id",
        "untaxed_base_amount",
    )
    def _compute_amount(self):
        for line in self:
            currency = line.currency_id or (line.move_id.currency_id if line.move_id else False)
            if line.calculation_type == "percentage":
                base_amount = line.untaxed_base_amount or 0.0
                # FE 4.4 exige MontoCargo positivo. El signo contable se gestiona
                # en account.move.line según el tipo de documento (factura/NC),
                # por lo que aquí siempre calculamos valor absoluto.
                amount = abs(base_amount) * ((line.percentage or 0.0) / 100.0)
                line.amount = currency.round(amount) if currency else amount
            else:
                manual_amount = max(line.amount_manual or 0.0, 0.0)
                line.amount = currency.round(manual_amount) if currency else manual_amount

    @api.onchange(
        "calculation_type",
        "move_id",
        "percentage",
        "amount_manual",
        "move_id.invoice_line_ids",
        "move_id.invoice_line_ids.price_subtotal",
        "move_id.invoice_line_ids.quantity",
        "move_id.invoice_line_ids.price_unit",
        "move_id.invoice_line_ids.discount",
        "move_id.invoice_line_ids.tax_ids",
    )
    def _onchange_recompute_amounts(self):
        """Mantiene monto en tiempo real antes de guardar."""
        self._fp_refresh_untaxed_base_amount_if_needed()
        self._compute_amount()

    def _fp_refresh_untaxed_base_amount_if_needed(self):
        for line in self:
            if line.calculation_type != "percentage" or not line.move_id:
                continue
            if not line.untaxed_base_amount:
                line.untaxed_base_amount = line.move_id._fp_get_untaxed_base_amount_for_other_charges()

    def _fp_get_detail_label(self):
        self.ensure_one()
        detail = (self.detail or "").strip()
        return detail or _("Otro cargo FE")

    @api.constrains("calculation_type", "percentage", "amount_manual", "account_id", "document_type", "document_type_other")
    def _check_positive_values(self):
        for line in self:
            if line.calculation_type == "percentage" and (line.percentage or 0.0) <= 0.0:
                raise ValidationError(_("El porcentaje de otros cargos debe ser mayor que cero."))
            if line.calculation_type == "amount" and (line.amount_manual or 0.0) <= 0.0:
                raise ValidationError(_("El monto manual de otros cargos debe ser mayor que cero."))
            if line.amount > 0.0 and not line.account_id:
                raise ValidationError(_("Debe seleccionar una cuenta contable en cada otro cargo."))
            if line.document_type == "99" and len((line.document_type_other or "").strip()) < 5:
                raise ValidationError(
                    _(
                        "Cuando Tipo documento es 99, debe indicar \"Tipo documento OTROS\" con al menos 5 caracteres."
                    )
                )


    @api.onchange("document_type")
    def _onchange_document_type_set_default_account(self):
        template_model = self.env["fp.other.charge.template"]
        for line in self:
            if line.document_type != "99":
                line.document_type_other = False
            if not line.move_id.company_id or not line.document_type:
                continue
            template = template_model._fp_find_template(line.move_id.company_id, line.document_type)
            if template:
                line.account_id = template.account_id
                if template.name:
                    line.detail = template.name
                line.calculation_type = template.calculation_type
                line.percentage = template.percentage
                line.amount_manual = template.amount_manual

    @api.model_create_multi
    def create(self, vals_list):
        template_model = self.env["fp.other.charge.template"]
        for vals in vals_list:
            if vals.get("account_id") or not vals.get("document_type"):
                continue
            move = self.env["account.move"].browse(vals.get("move_id"))
            template = template_model._fp_find_template(move.company_id, vals.get("document_type")) if move else False
            if template:
                vals["account_id"] = template.account_id.id
                vals.setdefault("calculation_type", template.calculation_type)
                if template.calculation_type == "percentage":
                    vals.setdefault("percentage", template.percentage)
                else:
                    vals.setdefault("amount_manual", template.amount_manual)
                if not vals.get("detail") and template.name:
                    vals["detail"] = template.name

            if vals.get("calculation_type") == "percentage" and not vals.get("untaxed_base_amount"):
                move = self.env["account.move"].browse(vals.get("move_id"))
                vals["untaxed_base_amount"] = move._fp_get_untaxed_base_amount_for_other_charges() if move else 0.0

        lines = super().create(vals_list)
        lines._fp_refresh_untaxed_base_amount_if_needed()
        lines.mapped("move_id")._fp_sync_other_charge_accounting_lines()
        return lines

    def write(self, vals):
        if vals.get("calculation_type") == "percentage" and "untaxed_base_amount" not in vals:
            for line in self.filtered(lambda l: l.move_id and not l.untaxed_base_amount):
                line.untaxed_base_amount = line.move_id._fp_get_untaxed_base_amount_for_other_charges()
        res = super().write(vals)
        self._fp_refresh_untaxed_base_amount_if_needed()
        self.mapped("move_id")._fp_sync_other_charge_accounting_lines()
        return res

    def unlink(self):
        moves = self.mapped("move_id")
        res = super().unlink()
        moves._fp_sync_other_charge_accounting_lines()
        return res
