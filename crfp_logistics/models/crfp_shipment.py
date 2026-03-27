import math
import base64
import logging
from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class CrfpShipment(models.Model):
    _name = 'crfp.shipment'
    _description = 'Export Shipment'
    _order = 'create_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Shipment Ref', readonly=True, default='New', copy=False)
    state = fields.Selection([
        ('draft', 'Draft'),
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
    ], string='Status', default='draft', tracking=True, index=True)

    # Commercial
    sale_order_id = fields.Many2one('sale.order', string='Sale Order')
    crfp_quotation_id = fields.Many2one('crfp.quotation', string='CRFP Quotation')
    partner_id = fields.Many2one('res.partner', string='Client', tracking=True)
    incoterm = fields.Selection([
        ('EXW', 'EXW'), ('FCA', 'FCA'), ('FOB', 'FOB'),
        ('CFR', 'CFR'), ('CIF', 'CIF'), ('CPT', 'CPT'),
        ('CIP', 'CIP'), ('DAP', 'DAP'), ('DDP', 'DDP'),
    ], string='Incoterm', tracking=True)

    # Invoices (reference only)
    proforma_invoice_id = fields.Many2one('account.move', string='Proforma Invoice')
    commercial_invoice_id = fields.Many2one('account.move', string='Commercial Invoice')

    # Logistics partners
    carrier_partner_id = fields.Many2one('res.partner', string='Carrier (Naviera)', tracking=True)
    forwarder_partner_id = fields.Many2one('res.partner', string='Forwarder', tracking=True)

    # Route
    port_origin_id = fields.Many2one('crfp.port', string='Port of Origin',
                                      default=lambda self: self._default_origin_port())
    port_destination_id = fields.Many2one('crfp.port', string='Port of Destination', tracking=True)
    container_type_id = fields.Many2one('crfp.container.type', string='Container Type')

    # Transport
    vessel_name = fields.Char(string='Vessel', tracking=True)
    voyage_number = fields.Char(string='Voyage')
    shipping_company = fields.Char(string='Shipping Company')
    freight_cost = fields.Float(string='Freight Cost (USD)', digits=(12, 2))

    # Reefer / SI fields
    temperature_set = fields.Float(string='Temperature Set (C)')
    ventilation = fields.Char(string='Ventilation',
                              help='e.g. 20 CBM/h or 25%')
    humidity = fields.Char(string='Relative Humidity (%)',
                           help='e.g. 85% or 80-90%')
    gps_device_id = fields.Char(string='GPS Device ID')
    commodity_description = fields.Text(string='Commodity Description')

    # Dates
    etd = fields.Date(string='ETD (Estimated Departure)', tracking=True)
    eta = fields.Date(string='ETA (Estimated Arrival)', tracking=True)
    atd = fields.Datetime(string='ATD (Actual Departure)', tracking=True)
    ata = fields.Datetime(string='ATA (Actual Arrival)', tracking=True)
    cutoff_date = fields.Datetime(string='Cutoff Date')

    # Future-ready
    consignee_id = fields.Many2one('res.partner', string='Consignee')
    notify_party_id = fields.Many2one('res.partner', string='Notify Party')

    # Management
    responsible_id = fields.Many2one('res.users', string='Responsible',
                                      default=lambda self: self.env.user, tracking=True)
    notes = fields.Html(string='Notes')

    # One2many
    line_ids = fields.One2many('crfp.shipment.line', 'shipment_id', string='Shipment Lines')
    container_ids = fields.One2many('crfp.shipment.container', 'shipment_id', string='Containers')
    booking_id = fields.Many2one('crfp.shipment.booking', string='Booking')
    document_ids = fields.One2many('crfp.shipment.document', 'shipment_id', string='Documents')
    checklist_ids = fields.One2many('crfp.shipment.checklist', 'shipment_id', string='Checklist')
    alert_ids = fields.One2many('crfp.shipment.alert', 'shipment_id', string='Alerts')
    log_ids = fields.One2many('crfp.shipment.log', 'shipment_id', string='Communication Log')
    tracking_event_ids = fields.One2many('crfp.tracking.event', 'shipment_id', string='Tracking Events')

    # Container number (from first container for easy list display)
    container_number = fields.Char(compute='_compute_container_number', store=True, string='Container #')

    # Computed
    total_boxes_planned = fields.Integer(compute='_compute_totals', store=True)
    total_boxes_actual = fields.Integer(compute='_compute_totals', store=True)
    total_pallets_planned = fields.Integer(compute='_compute_totals', store=True)
    total_pallets_actual = fields.Integer(compute='_compute_totals', store=True)
    total_net_weight_actual = fields.Float(compute='_compute_totals', store=True, digits=(12, 2))
    total_gross_weight_actual = fields.Float(compute='_compute_totals', store=True, digits=(12, 2))
    has_shortages = fields.Boolean(compute='_compute_totals', store=True)
    line_count = fields.Integer(compute='_compute_totals')
    docs_complete = fields.Boolean(compute='_compute_docs_progress')
    docs_pending_count = fields.Integer(compute='_compute_docs_progress')
    checklist_progress = fields.Float(compute='_compute_checklist_progress')
    alert_count = fields.Integer(compute='_compute_alert_count')

    @api.depends('container_ids.container_number')
    def _compute_container_number(self):
        for rec in self:
            first = rec.container_ids[:1]
            rec.container_number = first.container_number if first else ''

    @api.depends('line_ids.boxes_planned', 'line_ids.boxes_actual',
                 'line_ids.pallets_planned', 'line_ids.pallets_actual',
                 'line_ids.net_weight_actual', 'line_ids.gross_weight_actual',
                 'line_ids.has_shortage')
    def _compute_totals(self):
        for rec in self:
            lines = rec.line_ids
            rec.total_boxes_planned = sum(l.boxes_planned for l in lines)
            rec.total_boxes_actual = sum(l.boxes_actual for l in lines)
            rec.total_pallets_planned = sum(l.pallets_planned for l in lines)
            rec.total_pallets_actual = sum(l.pallets_actual for l in lines)
            rec.total_net_weight_actual = sum(l.net_weight_actual for l in lines)
            rec.total_gross_weight_actual = sum(l.gross_weight_actual for l in lines)
            rec.has_shortages = any(l.has_shortage for l in lines)
            rec.line_count = len(lines)

    @api.depends('document_ids.state', 'document_ids.is_required')
    def _compute_docs_progress(self):
        for rec in self:
            required = rec.document_ids.filtered(lambda d: d.is_required)
            done = required.filtered(lambda d: d.state in ('approved', 'na'))
            rec.docs_pending_count = len(required) - len(done)
            rec.docs_complete = len(required) == len(done) if required else False

    @api.depends('checklist_ids.state')
    def _compute_checklist_progress(self):
        for rec in self:
            total = len(rec.checklist_ids)
            done = len(rec.checklist_ids.filtered(lambda c: c.state in ('done', 'na')))
            rec.checklist_progress = (done / total * 100) if total else 0

    @api.depends('alert_ids.is_resolved')
    def _compute_alert_count(self):
        for rec in self:
            rec.alert_count = len(rec.alert_ids.filtered(lambda a: not a.is_resolved))

    def _default_origin_port(self):
        port = self.env['crfp.port'].search([('code', '=', 'MOI')], limit=1)
        return port.id if port else False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('crfp.shipment') or 'New'
            # Auto-fill from SO + Quotation on create
            if vals.get('sale_order_id') and not vals.get('partner_id'):
                so = self.env['sale.order'].browse(vals['sale_order_id'])
                quotation = self.env['crfp.quotation'].search([
                    ('sale_order_id', '=', so.id)
                ], limit=1)
                if not quotation and hasattr(so, 'crfp_quotation_id') and so.crfp_quotation_id:
                    quotation = so.crfp_quotation_id
                vals['partner_id'] = so.partner_id.id
                if quotation:
                    vals.setdefault('crfp_quotation_id', quotation.id)
                    vals.setdefault('incoterm', quotation.incoterm)
                    if quotation.port_id:
                        vals.setdefault('port_destination_id', quotation.port_id.id)
                    if quotation.container_type_id:
                        vals.setdefault('container_type_id', quotation.container_type_id.id)
                    vals.setdefault('etd', quotation.etd)
                    vals.setdefault('eta', quotation.eta)
                    if quotation.vessel_name:
                        vals.setdefault('vessel_name', quotation.vessel_name)
                    if quotation.freight_quote_id and quotation.freight_quote_id.carrier_partner_id:
                        vals.setdefault('carrier_partner_id', quotation.freight_quote_id.carrier_partner_id.id)
        return super().create(vals_list)

    @api.onchange('sale_order_id')
    def _onchange_sale_order_id(self):
        if not self.sale_order_id:
            return
        so = self.sale_order_id
        self.partner_id = so.partner_id
        # Find quotation: first try via SO link, then via crfp_quotation_id on SO
        quotation = self.env['crfp.quotation'].search([
            ('sale_order_id', '=', so.id)
        ], limit=1)
        if not quotation and hasattr(so, 'crfp_quotation_id') and so.crfp_quotation_id:
            quotation = so.crfp_quotation_id
        if quotation:
            self.crfp_quotation_id = quotation
            self.incoterm = quotation.incoterm
            self.port_destination_id = quotation.port_id
            self.container_type_id = quotation.container_type_id
            self.etd = quotation.etd
            self.eta = quotation.eta
            self.vessel_name = quotation.vessel_name or ''
            if quotation.freight_quote_id and quotation.freight_quote_id.carrier_partner_id:
                self.carrier_partner_id = quotation.freight_quote_id.carrier_partner_id

    def _create_lines_from_so(self):
        """Legacy method — calls the improved version without quotation."""
        self._create_lines_from_so_and_quotation(None)

    def _create_lines_from_so_and_quotation(self, quotation=None):
        """Create shipment lines from SO, using quotation data when available."""
        self.ensure_one()
        if not self.sale_order_id:
            return

        # Build a map of quotation lines by crfp_product_id for fast lookup
        q_lines_map = {}
        if quotation:
            for ql in quotation.line_ids:
                if ql.crfp_product_id:
                    q_lines_map[ql.crfp_product_id.id] = ql

        # Get first container if exists
        container = self.container_ids[:1]

        for sol in self.sale_order_id.order_line:
            if not sol.product_id:
                continue
            boxes_planned = int(sol.product_uom_qty)

            # Find crfp.product
            crfp_prod = self.env['crfp.product'].search([
                ('product_id', '=', sol.product_id.id)
            ], limit=1)

            # Try to get data from quotation line (most accurate)
            q_line = q_lines_map.get(crfp_prod.id) if crfp_prod else None

            if q_line:
                # Use quotation line data (preserves exact user input)
                net_kg = q_line.net_kg or (crfp_prod.net_kg if crfp_prod else 0)
                bpp = q_line.boxes_per_pallet or 66
            else:
                # Fallback: lookup from product and pallet config
                net_kg = crfp_prod.net_kg if crfp_prod else 0
                bpp = 66
                if crfp_prod:
                    pallet_cfg = self.env['crfp.pallet.config'].search([
                        ('product_keyword', 'ilike', crfp_prod.name)
                    ], limit=1)
                    if pallet_cfg:
                        bpp = pallet_cfg.boxes_per_pallet

            pallets_planned = math.ceil(boxes_planned / bpp) if bpp else 0

            self.env['crfp.shipment.line'].create({
                'shipment_id': self.id,
                'sale_order_line_id': sol.id,
                'product_id': sol.product_id.id,
                'crfp_product_id': crfp_prod.id if crfp_prod else False,
                'container_id': container.id if container else False,
                'boxes_planned': boxes_planned,
                'pallets_planned': pallets_planned,
                'boxes_per_pallet_planned': bpp,
                'net_weight_planned': boxes_planned * net_kg,
                'gross_weight_planned': boxes_planned * net_kg * 1.05,
                'price_unit_planned': sol.price_unit,
                'temperature_set': self.temperature_set or 0,
            })

    def _auto_load_documents(self):
        self.ensure_one()
        Doc = self.env['crfp.shipment.document']
        base_docs = [
            ('booking_request', 'generated'), ('booking_confirmation', 'received'),
            ('shipping_instructions', 'generated'), ('packing_list', 'generated'),
            ('commercial_invoice', 'odoo_ref'), ('bl_draft', 'received'),
            ('bl_original', 'received'), ('phytosanitary', 'received'),
            ('cert_origin', 'received'), ('customer_copy', 'generated'),
        ]
        if self.port_destination_id and self.port_destination_id.region == 'europe':
            base_docs.append(('eur1', 'received'))
        if self.incoterm in ('CIF', 'CIP', 'DAP', 'DDP'):
            base_docs.append(('insurance', 'received'))
        for doc_type, doc_source in base_docs:
            existing = Doc.search([('shipment_id', '=', self.id), ('doc_type', '=', doc_type)], limit=1)
            if not existing:
                Doc.create({
                    'shipment_id': self.id, 'doc_type': doc_type,
                    'doc_source': doc_source, 'is_required': True, 'state': 'pending',
                })

    def _auto_load_checklist(self):
        self.ensure_one()
        CL = self.env['crfp.shipment.checklist']
        tasks = [
            (10, 'logistics', 'Confirm carrier and booking details', True),
            (20, 'documentation', 'Prepare and send Shipping Instructions', True),
            (30, 'documentation', 'Obtain phytosanitary certificate', True),
            (40, 'documentation', 'Obtain certificate of origin', True),
            (50, 'logistics', 'Coordinate container pickup at plant', False),
            (60, 'logistics', 'Confirm packing and actual quantities', True),
            (70, 'documentation', 'Review BL draft from carrier', True),
            (80, 'documentation', 'Generate packing list from actuals', True),
            (90, 'commercial', 'Generate commercial invoice in Odoo', True),
            (100, 'logistics', 'Verify container gate-in at terminal', False),
            (110, 'logistics', 'Confirm departure (ATD)', False),
            (120, 'documentation', 'Send document package to customer', False),
            (130, 'logistics', 'Confirm arrival and delivery', False),
        ]
        for seq, cat, task_name, blocking in tasks:
            existing = CL.search([('shipment_id', '=', self.id), ('name', '=', task_name)], limit=1)
            if not existing:
                CL.create({
                    'shipment_id': self.id, 'name': task_name, 'sequence': seq,
                    'category': cat, 'is_blocking': blocking,
                    'responsible_id': self.responsible_id.id,
                })

    def _generate_commodity_description(self):
        self.ensure_one()
        descs = []
        for line in self.line_ids:
            pname = line.crfp_product_id.name if line.crfp_product_id else (
                line.product_id.display_name if line.product_id else 'Unknown')
            descs.append("%s - %d boxes / %d pallets" % (pname, line.boxes_planned, line.pallets_planned))
        self.commodity_description = '\n'.join(descs) if descs else ''

    # ── State transitions ──

    def action_request_space(self):
        self.ensure_one()
        if not self.carrier_partner_id:
            raise UserError('Set a Carrier before requesting space.')
        if not self.port_destination_id:
            raise UserError('Set a Destination Port before requesting space.')
        # Auto-create lines from SO if not yet created
        if self.sale_order_id and not self.line_ids:
            self._create_lines_from_so()
        # Auto-load documents and checklist
        self._auto_load_documents()
        self._auto_load_checklist()
        self._generate_commodity_description()
        self.write({'state': 'space_requested'})
        # Open email composer for pre-reserva
        return self.action_send_booking_crfarm()

    def action_request_booking(self):
        for rec in self:
            rec.write({'state': 'booking_requested'})

    def action_confirm_booking(self):
        for rec in self:
            if not rec.booking_id:
                raise UserError('Create or link a Booking before confirming.')
            rec.write({'state': 'booking_confirmed'})

    def action_send_si(self):
        for rec in self:
            if not rec.temperature_set:
                raise UserError('Set Temperature before sending SI.')
            if not rec.ventilation:
                raise UserError('Set Ventilation before sending SI.')
            rec.write({'state': 'si_sent'})

    def action_bl_draft_received(self):
        for rec in self:
            rec.write({'state': 'bl_draft_received'})

    def action_start_loading(self):
        for rec in self:
            rec.write({'state': 'loading'})

    def action_docs_final(self):
        for rec in self:
            if rec.line_ids:
                for line in rec.line_ids:
                    if not line.boxes_actual or line.boxes_actual <= 0:
                        pname = line.crfp_product_id.name if line.crfp_product_id else 'Unknown'
                        raise UserError('All lines must have actual boxes > 0. Check "%s".' % pname)
            rec.write({'state': 'docs_final'})

    def action_ship(self):
        for rec in self:
            if not rec.commercial_invoice_id:
                raise UserError('Link the Commercial Invoice before shipping.')
            rec.write({'state': 'shipped', 'atd': fields.Datetime.now()})

    def action_in_transit(self):
        for rec in self:
            rec.write({'state': 'in_transit'})

    def action_arrive(self):
        for rec in self:
            rec.write({'state': 'arrived', 'ata': fields.Datetime.now()})

    def action_deliver(self):
        for rec in self:
            rec.write({'state': 'delivered'})

    def action_close(self):
        for rec in self:
            rec.write({'state': 'closed'})

    # ── Email actions ──

    def action_send_booking_crfarm(self):
        self.ensure_one()
        body = (
            "<h3>BOOKING REQUEST - CR FARM PRODUCTS VYM S.A</h3>"
            "<p><b>Shipper:</b> CR FARM PRODUCTS VYM Y M S.A.</p>"
            "<p><b>Origin:</b> %(origin)s</p>"
            "<p><b>Destination:</b> %(dest)s</p>"
            "<p><b>ETD Requested:</b> %(etd)s</p>"
            "<p><b>Equipment:</b> 1x %(equip)s</p>"
            "<hr/>"
            "<p><b>Temperature:</b> %(temp)s °C</p>"
            "<p><b>Ventilation:</b> %(vent)s</p>"
            "<p><b>Relative Humidity:</b> %(humid)s</p>"
            "<hr/>"
            "<p><b>Commodity:</b> %(commodity)s</p>"
            "<p><b>Est. Pallets:</b> %(pallets)d / <b>Est. Boxes:</b> %(boxes)d</p>"
            "<br/><p>Best regards,<br/><b>CR Farm Products VYM S.A.</b></p>"
        ) % {
            'origin': self.port_origin_id.name or 'Puerto Moin, Costa Rica',
            'dest': self.port_destination_id.name or '',
            'etd': self.etd or 'TBD',
            'equip': self.container_type_id.name or '40ft HC Reefer',
            'temp': self.temperature_set if self.temperature_set else 'TBD',
            'vent': self.ventilation or 'TBD',
            'humid': self.humidity or 'TBD',
            'commodity': self.commodity_description or 'Fresh tropical roots and vegetables',
            'pallets': self.total_pallets_planned or 0,
            'boxes': self.total_boxes_planned or 0,
        }
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mail.compose.message',
            'views': [[False, 'form']],
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_model': 'crfp.shipment',
                'default_res_ids': self.ids,
                'default_partner_ids': [self.carrier_partner_id.id] if self.carrier_partner_id else [],
                'default_subject': 'Booking Request - %s - %s' % (self.name, self.port_destination_id.name or ''),
                'default_body': body,
                'default_composition_mode': 'comment',
            },
        }

    def action_send_si_crfarm(self):
        self.ensure_one()
        booking_ref = self.booking_id.booking_reference if self.booking_id else 'TBD'
        consignee = self.consignee_id.name if self.consignee_id else (self.partner_id.name or '')
        notify = self.notify_party_id.name if self.notify_party_id else (self.partner_id.name or '')
        body = (
            "<h3>SHIPPING INSTRUCTIONS - CR FARM PRODUCTS VYM S.A</h3>"
            "<p><b>Booking Ref:</b> %(booking)s</p>"
            "<p><b>Shipper:</b> CR FARM PRODUCTS VYM Y M S.A. / RUC: 3-101-808635</p>"
            "<p><b>Consignee:</b> %(consignee)s</p>"
            "<p><b>Notify:</b> %(notify)s</p>"
            "<hr/>"
            "<p><b>Port of Loading:</b> %(pol)s</p>"
            "<p><b>Port of Discharge:</b> %(pod)s</p>"
            "<p><b>Vessel/Voyage:</b> %(vessel)s / %(voyage)s</p>"
            "<p><b>Container Type:</b> %(container)s</p>"
            "<hr/>"
            "<p><b>Temperature:</b> %(temp)s °C</p>"
            "<p><b>Ventilation:</b> %(vent)s</p>"
            "<p><b>Relative Humidity:</b> %(humid)s</p>"
            "<hr/>"
            "<p><b>Commodity:</b> %(commodity)s</p>"
            "<p><b>Est. Pallets:</b> %(pallets)d / <b>Est. Boxes:</b> %(boxes)d</p>"
            "<br/><p>Best regards,<br/><b>CR Farm Products VYM S.A.</b></p>"
        ) % {
            'booking': booking_ref,
            'consignee': consignee,
            'notify': notify,
            'pol': self.port_origin_id.name or 'Puerto Moin',
            'pod': self.port_destination_id.name or '',
            'vessel': self.vessel_name or '',
            'voyage': self.voyage_number or '',
            'container': self.container_type_id.name or '40ft HC Reefer',
            'temp': self.temperature_set if self.temperature_set else 'TBD',
            'vent': self.ventilation or 'TBD',
            'humid': self.humidity or 'TBD',
            'commodity': self.commodity_description or 'Fresh tropical roots and vegetables',
            'pallets': self.total_pallets_planned or 0,
            'boxes': self.total_boxes_planned or 0,
        }
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mail.compose.message',
            'views': [[False, 'form']],
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_model': 'crfp.shipment',
                'default_res_ids': self.ids,
                'default_partner_ids': [self.carrier_partner_id.id] if self.carrier_partner_id else [],
                'default_subject': 'Shipping Instructions - %s - %s' % (self.name, booking_ref),
                'default_body': body,
                'default_composition_mode': 'comment',
            },
        }

    def action_send_carrier_doc(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mail.compose.message',
            'views': [[False, 'form']],
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_model': 'crfp.shipment',
                'default_res_ids': self.ids,
                'default_partner_ids': [self.carrier_partner_id.id] if self.carrier_partner_id else [],
                'default_subject': '%s - Carrier Document' % self.name,
                'default_body': '<p>Please find attached the requested document.</p>',
                'default_composition_mode': 'comment',
            },
        }

    def action_send_export_package(self):
        """Send all export documents to client. Auto-attaches all document files."""
        self.ensure_one()
        partner_ids = [self.partner_id.id] if self.partner_id else []

        # Collect ALL attachments from ALL shipment documents
        all_attachment_ids = []
        doc_list_html = []
        for doc in self.document_ids:
            doc_label = dict(doc._fields['doc_type'].selection).get(doc.doc_type, doc.doc_type)
            if doc.attachment_ids:
                all_attachment_ids.extend(doc.attachment_ids.ids)
                doc_list_html.append('<li>%s (%d files)</li>' % (doc_label, len(doc.attachment_ids)))
            else:
                doc_list_html.append('<li style="color:#999;">%s — no file attached</li>' % doc_label)

        body = (
            "<h3>EXPORT DOCUMENT PACKAGE - %s</h3>"
            "<p>Dear %s,</p>"
            "<p>Please find attached the complete export documentation for shipment <b>%s</b>.</p>"
            "<p><b>Vessel:</b> %s<br/>"
            "<b>Voyage:</b> %s<br/>"
            "<b>ETD:</b> %s<br/>"
            "<b>Destination:</b> %s<br/>"
            "<b>Container:</b> %s</p>"
            "<p><b>Documents included:</b></p><ul>%s</ul>"
            "<p>Please confirm reception.</p>"
            "<p>Best regards,<br/><b>CR Farm Products VYM S.A.</b></p>"
        ) % (
            self.name,
            self.partner_id.name or 'Customer',
            self.name,
            self.vessel_name or '',
            self.voyage_number or '',
            self.etd or '',
            self.port_destination_id.name or '',
            self.container_number or '',
            ''.join(doc_list_html),
        )
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mail.compose.message',
            'views': [[False, 'form']],
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_model': 'crfp.shipment',
                'default_res_ids': self.ids,
                'default_partner_ids': partner_ids,
                'default_subject': 'Export Documents - %s - %s' % (self.name, self.partner_id.name or ''),
                'default_body': body,
                'default_attachment_ids': all_attachment_ids,
                'default_composition_mode': 'comment',
            },
        }

    # ── Create Booking from Shipment ──

    def action_create_booking(self):
        """Create a booking pre-filled from this shipment."""
        self.ensure_one()
        if self.booking_id:
            raise UserError('This shipment already has a booking linked.')
        freight_cost = 0
        if self.crfp_quotation_id and self.crfp_quotation_id.freight_quote_id:
            freight_cost = self.crfp_quotation_id.freight_quote_id.all_in_freight
        booking = self.env['crfp.shipment.booking'].create({
            'shipment_id': self.id,
            'carrier_partner_id': self.carrier_partner_id.id if self.carrier_partner_id else False,
            'vessel_name': self.vessel_name or '',
            'voyage_number': self.voyage_number or '',
            'container_type_id': self.container_type_id.id if self.container_type_id else False,
            'etd': self.etd,
            'eta': self.eta,
            'cutoff_date': self.cutoff_date,
            'freight_cost': freight_cost,
            'state': 'requested',
        })
        self.write({'booking_id': booking.id})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'crfp.shipment.booking',
            'res_id': booking.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # ── Navigation actions ──

    def action_view_sale_order(self):
        self.ensure_one()
        if not self.sale_order_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': self.sale_order_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_quotation(self):
        self.ensure_one()
        if not self.crfp_quotation_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'crfp.quotation',
            'res_id': self.crfp_quotation_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # ── Legacy helpers ──

    def action_load_from_sale_order(self):
        self.ensure_one()
        if not self.sale_order_id:
            raise UserError('Select a Sale Order first.')
        if self.line_ids:
            raise UserError('Shipment already has lines.')
        self._create_lines_from_so()

    def action_load_checklist_template(self):
        self.ensure_one()
        templates = self.env['crfp.checklist.template'].search([], limit=1)
        if not templates:
            self._auto_load_checklist()
            return
        for line in templates.line_ids:
            self.env['crfp.shipment.checklist'].create({
                'shipment_id': self.id, 'name': line.name,
                'sequence': line.sequence, 'category': line.category,
                'is_blocking': line.is_blocking,
                'responsible_id': self.responsible_id.id,
            })

    def action_generate_packing_list(self):
        """Generate packing list PDF and auto-attach to the packing_list document."""
        self.ensure_one()
        report = self.env.ref('crfp_logistics.action_report_packing_list')

        try:
            # Generate the PDF binary
            pdf_content, content_type = report._render_qweb_pdf(report.report_name, [self.id])

            # Create ir.attachment
            filename = 'PackingList-%s.pdf' % self.name
            attachment = self.env['ir.attachment'].create({
                'name': filename,
                'type': 'binary',
                'datas': base64.b64encode(pdf_content),
                'res_model': 'crfp.shipment',
                'res_id': self.id,
                'mimetype': 'application/pdf',
            })

            # Find the packing_list document and attach the PDF
            pl_doc = self.document_ids.filtered(lambda d: d.doc_type == 'packing_list')
            if pl_doc:
                pl_doc[0].write({
                    'attachment_ids': [(4, attachment.id)],
                    'state': 'ready',
                })

            self.message_post(
                body='Packing List PDF generated and attached.',
                attachment_ids=[attachment.id],
            )
        except Exception as e:
            _logger.warning('Could not auto-attach packing list: %s', e)

        # Return the report action so user can see/download
        return report.report_action(self)
