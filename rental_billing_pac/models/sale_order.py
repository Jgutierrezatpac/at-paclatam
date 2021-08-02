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
            for line in self.order_line:
                procurements = []
                qty = line._get_qty_procurement(False)
                group_id = self.env['procurement.group'].create(line._prepare_procurement_group_vals())
                line.order_id.procurement_group_id = group_id
                values = line._prepare_procurement_values(group_id=group_id)
                product_qty = line.product_uom_qty - qty
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

    # Inherited methods
    def _action_launch_stock_rule(self, previous_product_uom_qty=False):
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
            product_per_day_price = self.product_id.rental_pricing_ids.filtered(lambda p: p.unit == 'day')
            invoicing_date = self.env.context.get('invoice_to')
            delivery_pickings = self.order_id.mapped('picking_ids').filtered(
                lambda l: l.picking_type_id.code == 'outgoing' and l.date_done)
            if not delivery_pickings:
                raise Warning(_("No done Delivery found !"))
            for delivery in delivery_pickings:
                is_invoice_with_last_invoice_date = any(self.order_id.invoice_ids.mapped('last_invoiced_date'))
                charge_from_date = max(self.order_id.invoice_ids.mapped(
                    'last_invoiced_date')) if is_invoice_with_last_invoice_date else delivery.date_done
                duration = invoicing_date - charge_from_date
                duration_in_days = duration.days
                stock_move_for_product = delivery.move_ids_without_package.filtered(
                    lambda x: x.product_id.id == self.product_id.id)
                total_qty = sum(move_line.quantity_done for move_line in stock_move_for_product)
                quantity_charge = (total_qty * duration_in_days) * product_per_day_price.price
                total_price_charged += quantity_charge
                total_delivered_quantity_unit += total_qty
            return_pickings = self.order_id.mapped('picking_ids').filtered(
                lambda l: l.picking_type_id.code == 'incoming' and l.date_done)
            for return_picking in return_pickings:
                is_invoice_with_last_invoice_date = any(self.order_id.invoice_ids.mapped('last_invoiced_date'))
                return_charge_from_date = max(self.order_id.invoice_ids.mapped(
                    'last_invoiced_date')) if is_invoice_with_last_invoice_date and return_picking.date_done < max(
                    self.order_id.invoice_ids.mapped('last_invoiced_date')) else return_picking.date_done
                return_duration = invoicing_date - return_charge_from_date
                return_duration_in_days = return_duration.days
                return_stock_move_for_product = return_picking.move_ids_without_package.filtered(
                    lambda x: x.product_id.id == self.product_id.id)
                return_total_qty = sum(move_line.quantity_done for move_line in return_stock_move_for_product)
                return_quantity_charge = (return_total_qty * return_duration_in_days) * product_per_day_price.price
                total_return_price_charged += return_quantity_charge
                total_return_quantity_unit += return_total_qty
            total_charge_for_rental = total_price_charged - total_return_price_charged
            total_quantity_for_rental = total_delivered_quantity_unit - total_return_quantity_unit
            new_quantity = total_quantity_for_rental if total_quantity_for_rental else total_delivered_quantity_unit
            price_per_rental_quantity = total_charge_for_rental / new_quantity
            res['quantity'] = new_quantity
            res['price_unit'] = price_per_rental_quantity
        return res
