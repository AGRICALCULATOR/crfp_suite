from odoo import models, fields


class CrfpPort(models.Model):
    _name = 'crfp.port'
    _description = 'Export Destination Port'
    _order = 'region, name'

    code = fields.Char(string='Code', required=True, index=True,
                       help='Port code, e.g. RTM, MIA, ANR')
    name = fields.Char(string='Port Name', required=True)
    country = fields.Char(string='Country', required=True)
    region = fields.Selection([
        ('europe', 'Europe'),
        ('north_america', 'North America'),
        ('caribbean', 'Caribbean'),
        ('central_america', 'Central America'),
        ('south_america', 'South America'),
        ('asia', 'Asia'),
        ('other', 'Other'),
    ], string='Region', required=True, default='europe')
    active = fields.Boolean(default=True)
    notes = fields.Text(string='Notes')

    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'Port code must be unique.'),
    ]

    def name_get(self):
        return [(r.id, f"{r.code} - {r.name} ({r.country})") for r in self]
