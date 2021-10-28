from odoo import api, fields, models
from datetime import timedelta


class Product(models.Model):
    _inherit = 'product.product'

    def _get_unavailable_qty(self, fro, to=None, **kwargs):
        """
            Inherited to fix the base error of line.reservation_begin was empty!
        """

        def unavailable_qty(so_line):
            return so_line.product_uom_qty - so_line.qty_returned

        begins_during_period, ends_during_period, covers_period = self._get_active_rental_lines(fro, to, **kwargs)
        active_lines_in_period = begins_during_period + ends_during_period
        # Custom code for writing value if the sale line does not have reservation_begin
        for sale_line in active_lines_in_period:
            if not sale_line.reservation_begin:
                padding_timedelta_before = timedelta(hours=sale_line.product_id.preparation_time)
                new_value = sale_line.pickup_date - padding_timedelta_before if sale_line.pickup_date else fields.Datetime.now()
                sale_line.write({'reservation_begin': new_value})
        # ended custom code
        res = super(Product, self)._get_unavailable_qty(fro=fro)
        return res
