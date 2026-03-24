from odoo import models, fields, api


class CrfpFixedCost(models.Model):
    _name = 'crfp.fixed.cost'
    _description = 'CR Farm Fixed Operating Costs'

    name = fields.Char(string='Name', default='CR Farm Fixed Costs',
                       required=True)
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company,
                                 required=True)

    # All values in USD per container unless noted
    transport = fields.Float(string='Internal Transport (USD)', default=600.0,
                             help='Transport from farm/plant to port in CR')
    thc_origin = fields.Float(string='THC Origin (USD)', default=380.0,
                              help='Terminal Handling Charge at Puerto Moin')
    fumigation = fields.Float(string='Fumigation CR (USD)', default=180.0,
                              help='Phytosanitary fumigation')
    broker = fields.Float(string='Customs Broker CR (USD)', default=150.0,
                          help='Customs broker export fee')
    thc_dest = fields.Float(string='THC Destination (USD)', default=0.0)
    fumig_dest = fields.Float(string='Fumigation Dest. (USD)', default=0.0)
    inland_dest = fields.Float(string='Inland Delivery Dest. (USD)', default=0.0)
    insurance_pct = fields.Float(string='Insurance (% of EXW+Freight)',
                                 default=0.30, digits=(12, 2))
    duties_pct = fields.Float(string='Import Duties (% of CIF)',
                              default=0.0, digits=(12, 2),
                              help='Only applies for DDP incoterm')
    default_total_boxes = fields.Integer(string='Default Boxes per Container',
                                         default=1386)
    default_exchange_rate = fields.Float(string='Default Exchange Rate (CRC/USD)',
                                         default=503.0, digits=(12, 2))

    @api.model
    def get_fixed_costs(self, company_id=None):
        """Return the fixed costs record for the given company (or current)."""
        domain = [('company_id', '=', company_id or self.env.company.id)]
        record = self.search(domain, limit=1)
        if not record:
            record = self.create({
                'company_id': company_id or self.env.company.id,
            })
        return record
