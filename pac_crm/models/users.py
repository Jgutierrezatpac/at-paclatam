# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class ResUsers(models.Model):
    _inherit = 'res.users'

    discounts = fields.Many2many('discount.sale', string="Authorized Discounts")