from odoo import fields, api, models, _


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    is_rental_operation_type = fields.Boolean(string="IS Rental")
