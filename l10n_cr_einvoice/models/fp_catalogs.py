from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class FpCabysCode(models.Model):
    _name = "fp.cabys.code"
    _description = "Código CABYS"
    _order = "code"

    code = fields.Char(string="Código", required=True)
    name = fields.Char(string="Descripción", required=True)
    active = fields.Boolean(default=True)

    _fp_cabys_code_unique = models.Constraint("UNIQUE(code)", "El código CABYS debe ser único.")

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get("install_mode"):
            return super().create(vals_list)

        records = self.browse()
        for vals in vals_list:
            code = vals.get("code")
            existing = self.search([("code", "=", code)], limit=1)
            if existing:
                existing.write({"name": vals.get("name", existing.name), "active": vals.get("active", existing.active)})
                records |= existing
            else:
                records |= super(FpCabysCode, self).create([vals])
        return records

    def name_get(self):
        return [(record.id, f"{record.code} - {record.name}") for record in self]


class FpEconomicActivity(models.Model):
    _name = "fp.economic.activity"
    _description = "Actividad Económica"
    _order = "code"

    code = fields.Char(string="Código", required=True)
    name = fields.Char(string="Descripción", required=True)
    active = fields.Boolean(default=True)

    _fp_economic_activity_code_unique = models.Constraint(
        "UNIQUE(code)", "El código de actividad económica debe ser único."
    )

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get("install_mode"):
            return super().create(vals_list)

        records = self.browse()
        for vals in vals_list:
            code = vals.get("code")
            existing = self.search([("code", "=", code)], limit=1)
            if existing:
                existing.write({"name": vals.get("name", existing.name), "active": vals.get("active", existing.active)})
                records |= existing
            else:
                records |= super(FpEconomicActivity, self).create([vals])
        return records

    def name_get(self):
        return [(record.id, f"{record.code} - {record.name}") for record in self]


class FpProvince(models.Model):
    _name = "fp.province"
    _description = "Provincia"
    _order = "code"

    code = fields.Char(string="Código", required=True)
    name = fields.Char(string="Nombre", required=True)
    active = fields.Boolean(default=True)

    canton_ids = fields.One2many("fp.canton", "province_id", string="Cantones")

    _fp_province_code_unique = models.Constraint("UNIQUE(code)", "El código de provincia debe ser único.")

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get("install_mode"):
            return super().create(vals_list)

        records = self.browse()
        for vals in vals_list:
            existing = self.search([("code", "=", vals.get("code"))], limit=1)
            if existing:
                existing.write({"name": vals.get("name", existing.name), "active": vals.get("active", existing.active)})
                records |= existing
            else:
                records |= super(FpProvince, self).create([vals])
        return records

    def name_get(self):
        return [(record.id, f"{record.code} - {record.name}") for record in self]


class FpCanton(models.Model):
    _name = "fp.canton"
    _description = "Cantón"
    _order = "province_id, code"

    code = fields.Char(string="Código", required=True)
    name = fields.Char(string="Nombre", required=True)
    province_id = fields.Many2one("fp.province", string="Provincia", required=True, ondelete="restrict")
    active = fields.Boolean(default=True)

    district_ids = fields.One2many("fp.district", "canton_id", string="Distritos")

    _fp_canton_code_unique_per_province = models.Constraint(
        "UNIQUE(province_id, code)",
        "El código de cantón debe ser único por provincia.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get("install_mode"):
            return super().create(vals_list)

        records = self.browse()
        for vals in vals_list:
            province_id = vals.get("province_id")
            existing = self.search([("province_id", "=", province_id), ("code", "=", vals.get("code"))], limit=1)
            if existing:
                existing.write({"name": vals.get("name", existing.name), "active": vals.get("active", existing.active)})
                records |= existing
            else:
                records |= super(FpCanton, self).create([vals])
        return records

    def name_get(self):
        return [(record.id, f"{record.code} - {record.name}") for record in self]


class FpDistrict(models.Model):
    _name = "fp.district"
    _description = "Distrito"
    _order = "canton_id, code"

    code = fields.Char(string="Código", required=True)
    name = fields.Char(string="Nombre", required=True)
    canton_id = fields.Many2one("fp.canton", string="Cantón", required=True, ondelete="restrict")
    province_id = fields.Many2one(
        "fp.province",
        string="Provincia",
        related="canton_id.province_id",
        store=True,
        readonly=True,
    )
    active = fields.Boolean(default=True)

    _fp_district_code_unique_per_canton = models.Constraint(
        "UNIQUE(canton_id, code)",
        "El código de distrito debe ser único por cantón.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get("install_mode"):
            return super().create(vals_list)

        records = self.browse()
        for vals in vals_list:
            canton_id = vals.get("canton_id")
            existing = self.search([("canton_id", "=", canton_id), ("code", "=", vals.get("code"))], limit=1)
            if existing:
                existing.write({"name": vals.get("name", existing.name), "active": vals.get("active", existing.active)})
                records |= existing
            else:
                records |= super(FpDistrict, self).create([vals])
        return records

    def name_get(self):
        return [(record.id, f"{record.code} - {record.name}") for record in self]


class FpOtherChargeTemplate(models.Model):
    _name = "fp.other.charge.template"
    _description = "Plantilla de Otros Cargos FE"
    _order = "company_id, document_type"

    company_id = fields.Many2one("res.company", string="Compañía", required=True, index=True)
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
    name = fields.Char(string="Detalle predeterminado")
    calculation_type = fields.Selection(
        [
            ("amount", "Monto"),
            ("percentage", "Porcentaje"),
        ],
        string="Cálculo predeterminado",
        required=True,
        default="amount",
    )
    percentage = fields.Float(string="Porcentaje predeterminado", digits=(16, 5))
    amount_manual = fields.Monetary(string="Monto predeterminado")
    currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)
    account_id = fields.Many2one(
        "account.account",
        string="Cuenta contable predeterminada",
        required=True,
        domain="[('company_ids', 'parent_of', company_id)]",
    )
    active = fields.Boolean(default=True)


    @api.constrains("calculation_type", "percentage", "amount_manual")
    def _check_default_amounts(self):
        for template in self:
            if template.calculation_type == "percentage" and (template.percentage or 0.0) <= 0.0:
                raise ValidationError(_("El porcentaje predeterminado debe ser mayor que cero."))
            if template.calculation_type == "amount" and (template.amount_manual or 0.0) <= 0.0:
                raise ValidationError(_("El monto predeterminado debe ser mayor que cero."))

    _fp_other_charge_template_unique = models.Constraint(
        "UNIQUE(company_id, document_type)",
        "Ya existe una plantilla para este tipo de documento y compañía.",
    )

    @api.model
    def _fp_find_template(self, company, document_type):
        if not company or not document_type:
            return self.browse()
        return self.search(
            [
                ("company_id", "=", company.id),
                ("document_type", "=", document_type),
                ("active", "=", True),
            ],
            limit=1,
        )

    def name_get(self):
        return [
            (
                record.id,
                f"[{record.document_type}] {record.account_id.display_name} ({record.company_id.display_name})",
            )
            for record in self
        ]
