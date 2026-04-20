import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class StatementSendWizard(models.TransientModel):
    _name = "statement.send.wizard"
    _description = "Enviar estado de cuenta por correo"

    partner_id = fields.Many2one("res.partner", required=True, string="Cliente")
    email_to = fields.Char(string="Para")
    email_cc = fields.Char(string="CC")
    subject = fields.Char(string="Asunto")
    body = fields.Html(string="Contenido", sanitize=False)

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        partner_id = values.get("partner_id") or self.env.context.get("default_partner_id")
        if partner_id:
            partner = self.env["res.partner"].browse(partner_id)
            target = partner._get_statement_target_emails() if partner else {}
            values.setdefault("partner_id", partner_id)
            values.setdefault("email_to", target.get("email_to") or partner.email or "")
            values.setdefault("email_cc", target.get("email_cc") or "")
            values.setdefault(
                "subject",
                _("Estado de cuenta - %(partner)s") % {"partner": partner.display_name or ""},
            )
            values.setdefault("body", self._default_body(partner))
        return values

    def _default_body(self, partner):
        company = self.env.company
        return _(
            "<p>Estimado(a) %(partner)s,</p>"
            "<p>Adjunto encontrará el estado de cuenta actualizado con %(company)s.</p>"
            "<p>Si ya realizó el pago, por favor omita este aviso. "
            "Para cualquier consulta, estamos a su disposición.</p>"
            "<p>Saludos cordiales,<br/>%(company)s</p>"
        ) % {"partner": partner.display_name or "", "company": company.name or ""}

    def action_send(self):
        self.ensure_one()
        partner = self.partner_id
        if not self.email_to:
            raise UserError(
                _('El contacto no tiene configurado un correo en "Correo para estados de cuenta".')
            )

        attachment = partner._render_statement_report_pdf()
        mail_values = {
            "subject": self.subject or _("Estado de cuenta - %(partner)s") % {"partner": partner.display_name},
            "body_html": self.body or "",
            "email_to": self.email_to,
            "email_cc": self.email_cc or False,
            "attachment_ids": [(6, 0, [attachment.id])],
            "auto_delete": True,
        }
        mail = self.env["mail.mail"].create(mail_values)
        mail.send()

        partner.message_post(
            body=_("Se envió un estado de cuenta por correo electrónico.")
            + _("<br/><strong>Para:</strong> ") + (self.email_to or "")
            + (_("<br/><strong>CC:</strong> ") + self.email_cc if self.email_cc else "")
            + _("<br/><strong>Asunto:</strong> ") + (self.subject or ""),
            attachment_ids=[attachment.id],
        )
        return {"type": "ir.actions.act_window_close"}
