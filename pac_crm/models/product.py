# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    rack_name = fields.Char(string="Rack number")
    rack_qty = fields.Integer(string="Rack Qty", default=1)

class Product(models.Model):
    _inherit = 'product.product'

    rack_name = fields.Char(string="Rack number")
    rack_qty = fields.Integer(string="Rack Qty", default=1)

# add in view