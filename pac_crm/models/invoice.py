# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class AccountMove(models.Model):
    _inherit = 'account.move'

    discount_ids = fields.Many2many("discount.sale", string="Discounts")
    amount_discount = fields.Monetary(string='Discount Total', store=True, compute='_compute_amount')

    @api.depends('discount_ids')
    def _compute_amount(self):
        super()._compute_amount()
        for move in self:
            sum_discounts = sum(dc.discount for dc in move.discount_ids) or 0.0

            amount_discount = 0
            for line in move.invoice_line_ids:
                amount_discount += (line.quantity * line.price_unit * sum_discounts) / 100
            move.amount_discount = amount_discount
            move.amount_total -= amount_discount
            move.amount_residual -= amount_discount