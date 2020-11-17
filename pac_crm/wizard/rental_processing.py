# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class RentalProcessing(models.TransientModel):
    _inherit = 'rental.order.wizard'

    @api.depends('rental_wizard_line_ids.qty_delivered')
    def _compute_has_lines_missing_stock(self):
        for wizard in self:
            wizard.has_lines_missing_stock = any(line.is_product_storable and line.status == 'pickup' and line.qty_delivered > line.product_id.qty_available for line in wizard.rental_wizard_line_ids)
class RentalProcessingLine(models.TransientModel):
    _inherit = 'rental.order.wizard.line'

    @api.model
    def _default_wizard_line_vals(self, line, status):
        # delay_price = line.product_id._compute_delay_price(fields.Datetime.now() - line.return_date)
        return {
            'order_line_id': line.id,
            'product_id': line.product_id.id,
            'qty_reserved': line.product_uom_qty,
            'qty_delivered': line.qty_delivered if status == 'return' else line.product_uom_qty - line.qty_delivered,
            'qty_returned': line.qty_returned if status == 'pickup' else line.qty_delivered - line.qty_returned,
        }

    

    def _apply(self):
        """Apply the wizard modifications to the SaleOrderLine.

        :return: message to log on the Sales Order.
        :rtype: str
        """
        msg = self._generate_log_message()
        for wizard_line in self:
            order_line = wizard_line.order_line_id
            if wizard_line.status == 'pickup' and wizard_line.qty_delivered > 0:
                order_line.update({
                    'product_uom_qty': max(order_line.product_uom_qty, order_line.qty_delivered + wizard_line.qty_delivered),
                    'qty_delivered': order_line.qty_delivered + wizard_line.qty_delivered
                })

                ######remove if statement
                order_line.pickup_date = fields.Datetime.now()
                ###### end
            elif wizard_line.status == 'return' and wizard_line.qty_returned > 0:
                if wizard_line.is_late:
                    # Delays facturation
                    order_line._generate_delay_line(wizard_line.qty_returned)

                order_line.update({
                    'qty_returned': order_line.qty_returned + wizard_line.qty_returned
                })
        return msg