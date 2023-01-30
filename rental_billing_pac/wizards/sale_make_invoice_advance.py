# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = "sale.advance.payment.inv"

    # Fields declaration
    advance_payment_method = fields.Selection(selection_add=[('rental_invoice', 'Rental Invoice')])
    invoice_to = fields.Datetime(string='Invoiced To', default=fields.Datetime.now())

    # Inherited methods
    def create_invoices(self):
        """
        Overwrite as we want to create invoice for selected dates.
        :return: base create_invoice is called.
        """
        if self.advance_payment_method == 'rental_invoice':
            sale_orders = self.env['sale.order'].browse(self._context.get('active_ids', []))
            sale_orders.with_context(invoice_to=self.invoice_to)._create_invoices(
                final=self.deduct_down_payments)
            if self._context.get('open_invoices', False):
                return sale_orders.action_view_invoice()
            return {'type': 'ir.actions.act_window_close'}
        return super().create_invoices()
