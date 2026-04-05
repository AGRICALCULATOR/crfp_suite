from odoo import models, fields


class CrfpIncotermMatrix(models.Model):
    _name = 'crfp.incoterm.matrix'
    _description = 'Incoterm Cost Matrix'
    _order = 'sequence'

    code = fields.Selection([
        ('EXW', 'EXW - Ex Works'),
        ('FCA', 'FCA - Free Carrier'),
        ('FOB', 'FOB - Free on Board'),
        ('CFR', 'CFR - Cost & Freight'),
        ('CIF', 'CIF - Cost, Insurance & Freight'),
        ('CPT', 'CPT - Carriage Paid To'),
        ('CIP', 'CIP - Carriage & Insurance Paid'),
        ('DAP', 'DAP - Delivered at Place'),
        ('DDP', 'DDP - Delivered Duty Paid'),
    ], string='Incoterm', required=True)
    sequence = fields.Integer(default=10)

    # 1 = seller pays, 0 = buyer pays
    inc_transport = fields.Boolean(string='Transport Internal', default=False)
    inc_fumigation = fields.Boolean(string='Fumigation CR', default=False)
    inc_thc_origin = fields.Boolean(string='THC Origin', default=False)
    inc_broker = fields.Boolean(string='Customs Broker CR', default=False)
    inc_freight = fields.Boolean(string='Ocean Freight', default=False)
    inc_insurance = fields.Boolean(string='Insurance', default=False)
    inc_thc_dest = fields.Boolean(string='THC Destination', default=False)
    inc_fumig_dest = fields.Boolean(string='Fumigation Dest.', default=False)
    inc_broker_dest = fields.Boolean(string='Broker Dest.', default=False)
    inc_inland_dest = fields.Boolean(string='Inland Delivery Dest.', default=False)
    inc_duties = fields.Boolean(string='Import Duties', default=False)

    code_unique = models.Constraint(
        'UNIQUE(code)',
        'Each incoterm can only have one matrix entry.',
    )
