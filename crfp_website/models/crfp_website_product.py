"""
CR Farm Website Product catalog model.

Separate from the internal crfp.product (pricing calculator),
this model holds the B2B-facing product data for the corporate website:
scientific names, packaging specs per market, available formats, photos.
"""
from odoo import models, fields


class CrfpWebsiteProduct(models.Model):
    _name = 'crfp.website.product'
    _description = 'CR Farm Website Product (B2B Catalog)'
    _order = 'sequence, name'

    # ── Identity ──
    name = fields.Char(string='Product Name', required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    category = fields.Selection([
        ('tubers', 'Roots & Tubers'),
        ('coconut', 'Coconut'),
        ('sugar_cane', 'Sugar Cane'),
        ('vegetables', 'Vegetables & Others'),
    ], string='Category', required=True, default='tubers')

    # ── Botanical info ──
    scientific_name = fields.Char(string='Scientific Name')
    also_known_as = fields.Char(string='Also Known As')
    production_season = fields.Char(string='Production Season', default='Year-round')

    # ── B2B Description ──
    description = fields.Text(string='B2B Description',
                              help='Product description for international buyers')

    # ── Packaging specs by market ──
    box_weight_eu_kg = fields.Float(
        string='Box Weight EU (kg)', digits=(12, 1),
        help='Net box weight for European market')
    box_weight_usa_ca_kg = fields.Float(
        string='Box Weight USA/CA (lbs)', digits=(12, 1),
        help='Net box weight for USA/Canada market (in lbs)')
    boxes_per_pallet = fields.Integer(
        string='Boxes / Pallet',
        help='Standard number of boxes per export pallet')
    pallets_per_container = fields.Integer(
        string="Pallets / 40' Container",
        help="Standard number of pallets per 40-foot container")

    # ── Available formats ──
    format_fresh = fields.Boolean(string='Fresh / Whole', default=True)
    format_peeled = fields.Boolean(string='Peeled')
    format_frozen = fields.Boolean(string='Frozen / IQF')
    format_halved = fields.Boolean(string='Halved')
    format_custom = fields.Char(string='Other Format')

    # ── Technical specs ──
    size_specs = fields.Char(string='Size / Caliber',
                             help='e.g. 300-600g; 5-15 cm length')
    tariff_code = fields.Char(string='HS Tariff Code',
                              help='Harmonized System tariff code for customs')

    # ── Media ──
    image_url = fields.Char(
        string='Product Image URL',
        help='Direct URL to product hero photo (publicly accessible)')
    onedrive_url = fields.Char(
        string='OneDrive Photo Gallery',
        help='Link to OneDrive folder with high-res product photos for buyers')

    # ── Internal ──
    notes = fields.Text(string='Internal Notes')
