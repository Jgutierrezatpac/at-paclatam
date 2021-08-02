# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError, Warning


class ReturnRentalProcessing(models.TransientModel):
    _name = 'return.rental.order.wizard'
    _description = 'Return Rental products'

    order_id = fields.Many2one('sale.order', required=True, ondelete='cascade')
    return_rental_wizard_line_ids = fields.One2many('return.rental.order.wizard.line', 'return_rental_order_wizard_id')
    has_late_lines = fields.Boolean(compute='_compute_has_late_lines')

    @api.onchange('order_id')
    def _get_wizard_lines(self):
        """Use Wizard lines to set by default the pickup/return value
        to the total pickup/return value expected"""
        rental_lines_ids = self.env.context.get('order_line_ids', [])
        rental_lines_to_process = self.env['sale.order.line'].browse(rental_lines_ids)

        # generate line values
        if rental_lines_to_process:
            lines_values = []
            for line in rental_lines_to_process:
                lines_values.append(
                    self.env['return.rental.order.wizard.line']._default_wizard_line_vals(line))
            self.return_rental_wizard_line_ids = [(6, 0, [])] + [(0, 0, vals) for vals in lines_values]

    @api.depends('return_rental_wizard_line_ids')
    def _compute_has_late_lines(self):
        for wizard in self:
            wizard.has_late_lines = wizard.return_rental_wizard_line_ids and any(
                line.is_late for line in wizard.return_rental_wizard_line_ids)

    def return_rental_products(self):
        """
            Create the rental returns for the rental order.
        """
        custom_picking_type_id = self.env['stock.picking.type'].search(
            [('is_rental_operation_type', '=', 'True'), ('code', '=', 'incoming')])
        # picking_type_id = self.picking_id.picking_type_id.return_picking_type_id.id or custom_picking_type_id.id
        return_move_lines = []
        return_counter = len(
            self.order_id.mapped('picking_ids').filtered(lambda l: l.picking_type_id.code == 'incoming')) + 1
        number_of_return = str(return_counter)
        for return_lines in self.return_rental_wizard_line_ids:
            if return_lines.qty_returned > return_lines.qty_pickedup:
                raise Warning(_("Return quantity exceeds the delivered quantity."))
            default_vals = (0, 0, {
                'product_id': return_lines.product_id.id,
                'product_uom_qty': return_lines.qty_returned,
                'product_uom': return_lines.product_id.uom_id.id,
                'state': 'draft',
                'date_expected': fields.Datetime.now(),
                'location_id': self.order_id.partner_job_site_id.rental_location_id.id or custom_picking_type_id.default_location_src_id.id,
                'location_dest_id': custom_picking_type_id.default_location_dest_id.id,
                'picking_type_id': custom_picking_type_id.id,
                'warehouse_id': custom_picking_type_id.warehouse_id.id,
                'name': _("Return of %s /" + number_of_return) % self.order_id.name,
                'procure_method': 'make_to_stock',
            })
            return_move_lines.append(default_vals)
        self.env['stock.picking'].create({
            'name': _("Return of %s/" + number_of_return) % self.order_id.name,
            'move_lines': return_move_lines,
            'picking_type_id': custom_picking_type_id.id,
            'state': 'draft',
            'origin': _("Return of %s/" + number_of_return) % self.order_id.name,
            'location_id': self.order_id.partner_job_site_id.rental_location_id.id or custom_picking_type_id.default_location_src_id.id,
            'location_dest_id': custom_picking_type_id.default_location_dest_id.id,
            'partner_id': self.order_id.partner_job_site_id.id,
            'sale_id': self.order_id.id})
        return {'type': 'ir.actions.act_window_close'}


class ReturnRentalProcessingLine(models.TransientModel):
    _name = 'return.rental.order.wizard.line'
    _description = 'Return RentalOrderLine transient representation'

    @api.model
    def _default_wizard_line_vals(self, line):
        # TODO : ADD our values
        total_product_quantity_delivered = 0
        total_product_quantity_returned = 0
        delivery_pickings = line.order_id.mapped('picking_ids').filtered(lambda l: l.picking_type_id.code == 'outgoing')
        return_pickings = line.order_id.mapped('picking_ids').filtered(lambda l: l.picking_type_id.code == 'incoming')
        for picking in delivery_pickings:
            for stock_move in picking.move_ids_without_package:
                if stock_move.product_id.id == line.product_id.id:
                    total_product_quantity_delivered += stock_move.quantity_done
        for picking in return_pickings:
            for stock_move in picking.move_ids_without_package:
                if stock_move.product_id.id == line.product_id.id:
                    total_product_quantity_returned += stock_move.quantity_done
        total_product_quantity = total_product_quantity_delivered - total_product_quantity_returned
        return {
            'order_line_id': line.id,
            'product_id': line.product_id.id,
            'qty_pickedup': total_product_quantity,
            'qty_returned': line.qty_returned,
            'is_late': line.is_late,
        }

    return_rental_order_wizard_id = fields.Many2one('return.rental.order.wizard', 'Return Rental Order Wizard',
                                                    required=True,
                                                    ondelete='cascade')
    order_line_id = fields.Many2one('sale.order.line', required=True)
    product_id = fields.Many2one('product.product', string='Product', required=True, readony=True)
    qty_pickedup = fields.Float("Picked-up")
    qty_returned = fields.Float("Returned")
    is_late = fields.Boolean(default=False)
