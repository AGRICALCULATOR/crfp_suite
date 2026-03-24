from odoo import models, fields


class CrfpBoxType(models.Model):
    _name = 'crfp.box.type'
    _description = 'Box / Packaging Type'
    _order = 'sequence, name'

    name = fields.Char(string='Description', required=True,
                       help='e.g. Caja Generica 18kg')
    brand = fields.Char(string='Brand / Client',
                        help='e.g. Generic, Mitrofresh, Sandy Tropic')
    cost = fields.Float(string='Cost per Box (USD)', required=True,
                        digits=(12, 2))
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    notes = fields.Text(string='Notes')
