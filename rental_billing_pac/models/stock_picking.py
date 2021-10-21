from odoo import fields, api, models


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    # Field declarations
    is_rental_operation_type = fields.Boolean(string="IS Rental")


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    @api.constrains('company_id')
    def _check_company(self):
        """
            Inherited to solve the issue of the multi company while validating the picking !
        """
        if not self.sale_id.is_rental_order:
            super(StockPicking, self)._check_company()
