from odoo import models, fields


class CrfpShipmentChecklist(models.Model):
    _name = 'crfp.shipment.checklist'
    _description = 'Shipment Checklist Task'
    _order = 'sequence, id'

    shipment_id = fields.Many2one('crfp.shipment', required=True, ondelete='cascade')
    name = fields.Char(string='Task', required=True)
    sequence = fields.Integer(default=10)
    state = fields.Selection([
        ('pending', 'Pending'),
        ('done', 'Done'),
        ('na', 'N/A'),
    ], string='Status', default='pending')
    date_due = fields.Date(string='Due Date')
    date_done = fields.Date(string='Completed Date')
    responsible_id = fields.Many2one('res.users', string='Responsible')
    category = fields.Selection([
        ('booking', 'Booking'),
        ('commercial', 'Commercial'),
        ('documentation', 'Documentation'),
        ('logistics', 'Logistics'),
        ('customs', 'Customs'),
        ('delivery', 'Delivery'),
    ], string='Category', default='logistics')
    is_blocking = fields.Boolean(string='Blocking',
                                  help='If checked, this task blocks shipment progress')
    notes = fields.Text(string='Notes')

    def action_done(self):
        self.write({'state': 'done', 'date_done': fields.Date.today()})

    def action_na(self):
        self.write({'state': 'na'})

    def action_reset(self):
        self.write({'state': 'pending', 'date_done': False})
