from odoo import models, fields


class CrfpContainerType(models.Model):
    _name = 'crfp.container.type'
    _description = 'Container Type'
    _order = 'sequence, name'

    code = fields.Char(string='Code', required=True,
                       help='e.g. 40hrf, 40hc, 20dry')
    name = fields.Char(string='Name', required=True,
                       help='e.g. 40ft HC Reefer')
    capacity_boxes = fields.Integer(string='Standard Box Capacity',
                                    help='Default number of boxes this container holds')
    is_reefer = fields.Boolean(string='Reefer', default=False)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _code_unique = models.Constraint(
        'UNIQUE(code)',
        'Container type code must be unique.',
    )
