from odoo import models, fields


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    peso_neto = fields.Float(
        string='Peso neto',
        digits=(12, 2),
        help='Net weight in kilograms',
    )
    peso_total = fields.Float(
        string='Peso total',
        digits=(12, 2),
        help='Gross weight in kilograms (includes packaging)',
    )
