from odoo import models, fields


class CrfpChecklistTemplate(models.Model):
    _name = 'crfp.checklist.template'
    _description = 'Checklist Template'
    _order = 'name'

    name = fields.Char(string='Template Name', required=True,
                       help='e.g. FOB Europe, CIF North America')
    incoterm_filter = fields.Selection([
        ('EXW', 'EXW'), ('FCA', 'FCA'), ('FOB', 'FOB'),
        ('CFR', 'CFR'), ('CIF', 'CIF'), ('CPT', 'CPT'),
        ('CIP', 'CIP'), ('DAP', 'DAP'), ('DDP', 'DDP'),
    ], string='Incoterm', help='Optional: filter template by incoterm')
    line_ids = fields.One2many('crfp.checklist.template.line', 'template_id',
                                string='Checklist Items')
    notes = fields.Text(string='Notes')
    active = fields.Boolean(default=True)


class CrfpChecklistTemplateLine(models.Model):
    _name = 'crfp.checklist.template.line'
    _description = 'Checklist Template Line'
    _order = 'sequence, id'

    template_id = fields.Many2one('crfp.checklist.template', required=True,
                                   ondelete='cascade')
    name = fields.Char(string='Task', required=True)
    sequence = fields.Integer(default=10)
    category = fields.Selection([
        ('commercial', 'Commercial'),
        ('documentation', 'Documentation'),
        ('logistics', 'Logistics'),
        ('customs', 'Customs'),
        ('delivery', 'Delivery'),
    ], string='Category', default='logistics')
    is_blocking = fields.Boolean(string='Blocking', default=False)
    blocks_state = fields.Selection([
        ('space_requested', 'Space Requested'),
        ('booking_requested', 'Booking Requested'),
        ('booking_confirmed', 'Booking Confirmed'),
        ('si_sent', 'SI Sent'),
        ('bl_draft_received', 'BL Draft Received'),
        ('loading', 'Loading'),
        ('docs_final', 'Docs Final'),
        ('shipped', 'Shipped'),
        ('in_transit', 'In Transit'),
        ('arrived', 'Arrived'),
        ('delivered', 'Delivered'),
        ('closed', 'Closed'),
    ], string='Blocks State',
       help='Which shipment state this task blocks')
