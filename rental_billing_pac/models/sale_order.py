from odoo import fields, api, models, _
from odoo.exceptions import UserError, Warning


class SaleOrder(models.Model):
    _inherit = "sale.order"

    # Field declarations.
    partner_job_site_id = fields.Many2one('res.partner', string='Job site Address')
    return_count = fields.Integer(string='Return Orders', compute='_compute_return_picking_ids')

    # Compute methods
    @api.depends('picking_ids')
    def _compute_picking_ids(self):
        for order in self:
            if order.is_rental_order:
                order.delivery_count = len(
                    order.mapped('picking_ids').filtered(lambda l: l.picking_type_id.code == 'outgoing'))
            else:
                order.delivery_count = len(order.picking_ids)

    def _compute_return_picking_ids(self):
        for order in self:
            order.return_count = len(
                order.mapped('picking_ids').filtered(lambda l: l.picking_type_id.code == 'incoming'))

    # On change methods
    @api.onchange('partner_id')
    def _onchange_vendors(self):
        filtered_child = self.partner_id.child_ids.filtered(lambda r: r.type == 'rental').ids
        if self.partner_id.rental_location_id:
            filtered_child.append(self.partner_id.id)
        return {
            'domain': {
                'partner_job_site_id': [
                    ('id', 'in', filtered_child)
                ]}
        }

    # Inherited Methods
    def action_view_delivery(self):
        res = super(SaleOrder, self).action_view_delivery()
        if self.is_rental_order and res['domain']:
            res['domain'].append(('picking_type_id.code', '=', 'outgoing'))
        return res

    def _action_confirm(self):
        is_order_rental = True if self.is_rental_order else False
        if is_order_rental:
            procurements = []
            for line in self.order_line:
                group_id = line._get_procurement_group()
                if not group_id:
                    group_id = self.env['procurement.group'].create(line._prepare_procurement_group_vals())
                    line.order_id.procurement_group_id = group_id
                values = line._prepare_procurement_values(group_id=group_id)
                product_qty = line.product_uom_qty
                line_uom = line.product_uom
                quant_uom = line.product_id.uom_id
                product_qty, procurement_uom = line_uom._adjust_uom_quantities(product_qty, quant_uom)
                procurements.append(self.env['procurement.group'].Procurement(
                    line.product_id, product_qty, procurement_uom,
                    line.order_id.partner_shipping_id.property_stock_customer,
                    line.name, line.order_id.name, line.order_id.company_id, values))
            if procurements:
                self.env['procurement.group'].run(procurements)
            return super(SaleOrder, self)._action_confirm()
        else:
            return super(SaleOrder, self)._action_confirm()

    def _prepare_invoice(self):
        """
            This method is overwrite so that we can add the new field,
            for last invoice date.
        """
        res = super(SaleOrder, self)._prepare_invoice()
        if self.env.context.get('invoice_to') and self.is_rental_order:
            res.update({'last_invoiced_date': self.env.context.get('invoice_to')})
        return res

    # Custom methods
    def action_view_returns(self):
        '''
            This function returns an action that display existing return orders
            of given sales order ids. It can either be a in a list or in a form
            view, if there is only one delivery order to show.
        '''
        action = self.env.ref('stock.action_picking_tree_all').read()[0]
        pickings = self.mapped('picking_ids').filtered(lambda l: l.picking_type_id.code == 'incoming')
        if len(pickings) > 1:
            action['domain'] = [('id', 'in', pickings.ids)]
        elif pickings:
            form_view = [(self.env.ref('stock.view_picking_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = pickings.id
        picking_id = pickings.filtered(lambda l: l.picking_type_id.code == 'incoming')
        if picking_id:
            picking_id = picking_id[0]
        else:
            picking_id = pickings[0]
        action['context'] = dict(self._context, default_partner_id=self.partner_id.id,
                                 default_picking_type_id=picking_id.picking_type_id.id, default_origin=self.name,
                                 default_group_id=picking_id.group_id.id)
        return action

    def open_rental_return(self):
        lines_to_return = self.order_line.filtered(
            lambda r: r.is_rental)
        return self._open_rental_return_wizard(lines_to_return.ids)

    def _open_rental_return_wizard(self, order_line_ids):
        context = {
            'order_line_ids': order_line_ids,
            'default_order_id': self.id,
        }
        return {
            'name': _('Return Rental products'),
            'view_mode': 'form',
            'res_model': 'return.rental.order.wizard',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': context
        }


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    # Field declarations
    qty_returned = fields.Float("Returned", store=True, compute='_compute_qty_returned')

    # Inherited Methods
    @api.depends('move_ids.state', 'move_ids.scrapped', 'move_ids.product_uom_qty', 'move_ids.product_uom')
    def _compute_qty_returned(self):
        """
            Compute inherited so that we can add the value from new picking created.
        """
        for line in self:
            if line.is_rental:
                return_pickings = line.order_id.mapped('picking_ids').filtered(
                    lambda l: l.picking_type_id.code == 'incoming' and l.date_done)
                return_stock_move_for_product = return_pickings.move_ids_without_package.filtered(
                    lambda x: x.product_id.id == line.product_id.id)
                return_total_qty = sum(move_line.quantity_done for move_line in return_stock_move_for_product)
                if return_total_qty:
                    line.write({'qty_returned': return_total_qty})

    @api.depends('move_ids.state', 'move_ids.scrapped', 'move_ids.product_uom_qty', 'move_ids.product_uom')
    def _compute_qty_delivered(self):
        """
            Inherited so that even the sale line with rental product can have delivery status.
        """
        for line in self:
            if line.is_rental:
                qty = 0.0
                outgoing_moves, incoming_moves = line._get_outgoing_incoming_moves()
                for move in outgoing_moves:
                    if move.state != 'done':
                        continue
                    qty += move.product_uom._compute_quantity(move.product_uom_qty, line.product_uom,
                                                              rounding_method='HALF-UP')
                for move in incoming_moves:
                    if move.state != 'done':
                        continue
                    qty -= move.product_uom._compute_quantity(move.product_uom_qty, line.product_uom,
                                                              rounding_method='HALF-UP')
                line.qty_delivered = qty
            else:
                super(SaleOrderLine, self)._compute_qty_delivered()

    def _action_launch_stock_rule(self, previous_product_uom_qty=False):
        """
            Inherited so that the base code does not disable stock moves for rental order lines.
        """
        is_rental = True if self.order_id.is_rental_order else False
        if is_rental:
            return True
        else:
            return super(SaleOrderLine, self)._action_launch_stock_rule()

    def _prepare_invoice_line(self):
        """
            Overwrite so that we can change the default qty of invoice_lines.
            :return: res dictionary having vals for invoice_lines.
        """
        res = super()._prepare_invoice_line()
        if self.order_id.is_rental_order and self.env.context.get('invoice_to'):
            total_delivered_quantity_unit = 0
            total_price_charged = 0
            total_return_quantity_unit = 0
            total_return_price_charged = 0
            invoicing_date = self.env.context.get('invoice_to')
            delivery_pickings = self.order_id.mapped('picking_ids').filtered(
                lambda l: l.picking_type_id.code == 'outgoing' and l.date_done)
            if not delivery_pickings:
                raise Warning(_("No done Delivery found !"))
            for delivery in delivery_pickings:
                is_invoice_with_last_invoice_date = any(self.order_id.invoice_ids.mapped('last_invoiced_date'))
                charge_from_date = max(self.order_id.invoice_ids.mapped(
                    'last_invoiced_date')) if is_invoice_with_last_invoice_date else delivery.date_done
                rental_pricing_id = self.product_id._get_best_pricing_rule(
                    pickup_date=charge_from_date,
                    return_date=invoicing_date,
                    pricelist=self.order_id.pricelist_id,
                    company=self.company_id)
                duration_dict = self.env['rental.pricing']._compute_duration_vals(charge_from_date,
                                                                                  invoicing_date)
                if rental_pricing_id:
                    values = {
                        'duration_unit': rental_pricing_id.unit,
                        'duration': duration_dict[rental_pricing_id.unit]
                    }
                else:
                    values = {
                        'duration_unit': 'day',
                        'duration': duration_dict['day']
                    }
                unit_price = self.product_id.lst_price
                if rental_pricing_id:
                    unit_price = rental_pricing_id._compute_price(values.get('duration'), values.get('duration_unit'))
                stock_move_for_product = delivery.move_ids_without_package.filtered(
                    lambda x: x.product_id.id == self.product_id.id)
                total_qty = sum(move_line.quantity_done for move_line in stock_move_for_product)
                quantity_charge = total_qty * unit_price
                total_price_charged += quantity_charge
                total_delivered_quantity_unit += total_qty
            return_pickings = self.order_id.mapped('picking_ids').filtered(
                lambda l: l.picking_type_id.code == 'incoming' and l.date_done)
            for return_picking in return_pickings:
                is_invoice_with_last_invoice_date = any(self.order_id.invoice_ids.mapped('last_invoiced_date'))
                return_charge_from_date = max(self.order_id.invoice_ids.mapped(
                    'last_invoiced_date')) if is_invoice_with_last_invoice_date and return_picking.date_done < max(
                    self.order_id.invoice_ids.mapped('last_invoiced_date')) else return_picking.date_done
                return_rental_pricing_id = self.product_id._get_best_pricing_rule(
                    pickup_date=return_charge_from_date,
                    return_date=invoicing_date,
                    pricelist=self.order_id.pricelist_id,
                    company=self.company_id)
                return_duration_dict = self.env['rental.pricing']._compute_duration_vals(return_charge_from_date,
                                                                                         invoicing_date)
                if return_rental_pricing_id:
                    return_values = {
                        'duration_unit': return_rental_pricing_id.unit,
                        'duration': return_duration_dict[return_rental_pricing_id.unit]
                    }
                else:
                    return_values = {
                        'duration_unit': 'day',
                        'duration': return_duration_dict['day']
                    }
                return_unit_price = self.product_id.lst_price
                if return_rental_pricing_id:
                    return_unit_price = return_rental_pricing_id._compute_price(return_values.get('duration'),
                                                                                return_values.get('duration_unit'))
                return_stock_move_for_product = return_picking.move_ids_without_package.filtered(
                    lambda x: x.product_id.id == self.product_id.id)
                return_total_qty = sum(move_line.quantity_done for move_line in return_stock_move_for_product)
                return_quantity_charge = return_total_qty * return_unit_price
                total_return_price_charged += return_quantity_charge
                total_return_quantity_unit += return_total_qty
            total_charge_for_rental = total_price_charged - total_return_price_charged
            total_quantity_for_rental = total_delivered_quantity_unit - total_return_quantity_unit
            new_quantity = total_quantity_for_rental if total_quantity_for_rental else total_delivered_quantity_unit
            price_per_rental_quantity = total_charge_for_rental / new_quantity
            res['quantity'] = new_quantity
            res['price_unit'] = price_per_rental_quantity
        return res
