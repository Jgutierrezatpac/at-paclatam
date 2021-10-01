from odoo import fields, api, models, _
from odoo.exceptions import UserError, Warning


class StockMove(models.Model):
    _inherit = "stock.move"

    # Inherited methods.
    def _get_new_picking_values(self):
        """ return create values for new picking that will be linked with group
        of moves in self.
        """
        res = super(StockMove, self)._get_new_picking_values()
        is_rental = False
        if self.sale_line_id:
            is_rental = self.sale_line_id.order_id.is_rental_order
        if is_rental:
            rental_partner = self.sale_line_id.order_id.partner_job_site_id
            picking_type_id = self.env['stock.picking.type'].search(
                [('is_rental_operation_type', '=', 'True'), ('code', '=', 'outgoing')])
            is_picking_type_available = picking_type_id or picking_type_id.default_location_src_id
            if not is_picking_type_available:
                raise Warning(_("No operation type for rental found !"))
            res.update({
                'partner_id': rental_partner.id,
                'picking_type_id': picking_type_id.id,
                'location_id': self.mapped('location_id').id or picking_type_id.default_location_src_id.id,
                'location_dest_id': rental_partner.rental_location_id.id or picking_type_id.default_location_dest_id.id,
                'state': 'draft',
            })
        return res

    def _search_picking_for_assignation(self):
        self.ensure_one()
        is_rental = False
        if self.sale_line_id:
            is_rental = self.sale_line_id.order_id.is_rental_order
        if is_rental:
            rental_partner = self.sale_line_id.order_id.partner_job_site_id
            picking_type_id = self.env['stock.picking.type'].search(
                [('is_rental_operation_type', '=', 'True'), ('code', '=', 'outgoing')])
            picking = self.env['stock.picking'].search([
                ('group_id', '=', self.group_id.id),
                ('location_id', '=', self.mapped('location_id').id or picking_type_id.default_location_src_id.id),
                ('location_dest_id', '=',
                 rental_partner.rental_location_id.id or picking_type_id.default_location_dest_id.id),
                ('picking_type_id', '=', picking_type_id.id),
                ('printed', '=', False),
                ('immediate_transfer', '=', False),
                ('state', 'in', ['draft', 'confirmed', 'waiting', 'partially_available', 'assigned'])], limit=1)
            return picking
        else:
            return super(StockMove, self)._search_picking_for_assignation()
