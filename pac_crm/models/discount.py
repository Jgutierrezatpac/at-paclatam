# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class CrmLead(models.Model):
    _name = 'discount.sale'
    _description = "Sale Discount"

    name = fields.Char(string="Discount name")
    discount  = fields.Float(string="discount %")
    company_id = fields.Many2one("res.company", string="Company")
