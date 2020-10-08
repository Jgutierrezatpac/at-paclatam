# -*- coding: utf-8 -*-


from odoo import api, fields, models, _, SUPERUSER_ID
import base64
import xlrd
from odoo.exceptions import UserError
from odoo.tools import float_round
import math

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    discount_ids = fields.Many2many("discount.sale", string="Discounts", store=True)
    need_authorize = fields.Boolean(string="Discount superior authorization",store=True,compute="_compute_authorization")
    is_authorize = fields.Boolean(string="Authorization",store=True, )
    amount_discount = fields.Monetary(string='Discount Total', store=True, compute='_amount_all')

    is_select = fields.Boolean(string="Crm Calculate Selection")
    is_used = fields.Boolean(string="Used products")

    file_name = fields.Char(string='File Name')
    file_data = fields.Binary('import file', )

    total_weight = fields.Float(string="Total Weight", compute="_compute_total_weight_parts")
    total_part = fields.Float(string="Total Parts", compute="_compute_total_weight_parts")

    replacement_price = fields.Monetary(string='Replacement', store=True, compute='_compute_total_weight_parts') 

    @api.depends('order_line')
    def _compute_total_weight_parts(self):
        for order in self:
            weight = parts = replacement = 0
            for line in order.order_line:
                weight += line.total_weight 
                parts += line.product_uom_qty
                replacement += (line.product_uom_qty * line.product_id.lst_price)
            order.total_weight = weight 
            order.total_part = parts
            order.replacement_price = replacement

    @api.depends('discount_ids')
    def _compute_authorization(self):
        sales_manager = self.env.ref('sales_team.group_sale_manager').users
        
        # user_id = self.env.user
        for order in self:
            
            for discount in order.discount_ids:
                if order.user_id not in sales_manager and discount._origin not in order.user_id.discounts:
                    order.need_authorize = True
                else:
                    order.need_authorize = False

    def import_file(self):
        self.ensure_one()
        data_file = base64.b64decode(self.file_data)

        book = xlrd.open_workbook(file_contents=data_file or b'')
        worksheet = book.sheet_by_index(0)
        first_row = []
        for col in range(worksheet.ncols):
            first_row.append( worksheet.cell_value(0,col) )
        archive_lines = []
        for row in range(1, worksheet.nrows):
            elm = {}
            for col in range(worksheet.ncols):
                elm[first_row[col]]=worksheet.cell_value(row,col)

            archive_lines.append(elm)

        # create the method
        self.valid_product_code(archive_lines)

        for line in archive_lines:
            code = str(line.get('codigo_producto',"")).strip()
            product_id = self.env['product.product'].search([('default_code','=',code)])
            quantity = line.get(u'cantidad',0)
            if self and product_id:
                vals = {
                    'order_id': self.id,
                    'product_id': product_id.id,
                    'product_uom_qty': float(quantity),
                    'price_unit': product_id.list_price,
                    'product_uom': product_id.product_tmpl_id.uom_po_id.id,
                    'name': product_id.name,
                    'weight': product_id.weight,
                    'total_weight': product_id.weight * float(quantity)
                }
                self.env['sale.order.line'].create(vals)
 
    def valid_product_code(self, archive_lines):
        products = self.env['product.product']
        for line in archive_lines:
            code = str(line.get('codigo_producto',"")).strip()
            product_id = products.search([('default_code','=',code)])
            if not product_id:
                raise UserError("The product code of line %s can't be found in the system."%code)

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            seq_date = None
            if 'date_order' in vals:
                seq_date = fields.Datetime.context_timestamp(self, fields.Datetime.to_datetime(vals['date_order']))
            if vals['is_rental_order']:
                code = self.env.ref('pac_crm.rental_order_sequence').code
                name = self.env['ir.sequence'].with_context(force_company=vals['company_id']).next_by_code(code, sequence_date=seq_date) or _('New')
                while self.env['sale.order'].search_count([('name', '=', name)]) >= 1:
                    code = self.env.ref('pac_crm.rental_order_sequence').code
                    name = self.env['ir.sequence'].with_context(force_company=vals['company_id']).next_by_code(code, sequence_date=seq_date) or _('New')
                vals['name'] = name
        return super(SaleOrder, self).create(vals)

   

    @api.depends('order_line.price_total', 'discount_ids')
    def _amount_all(self):
        """
        Compute the total amounts of the SO.
        """
        for order in self:
            sum_discounts = 0.0
            for dc in order.discount_ids:
                sum_discounts += dc.discount

            amount_untaxed = amount_tax = amount_discount = 0.0
            for line in order.order_line:
                amount_untaxed += line.price_subtotal
                amount_tax += line.price_tax
                amount_discount += (line.product_uom_qty * line.price_unit * sum_discounts) / 100
            order.update({
                'amount_untaxed': amount_untaxed,
                'amount_tax': amount_tax,
                'amount_discount': amount_discount,
                'amount_total': amount_untaxed + amount_tax - amount_discount,
            })

    def _prepare_invoice(self,):
        invoice_vals = super(SaleOrder, self)._prepare_invoice()
        invoice_vals.update({
            'discount_ids': self.discount_ids,
        })
        return invoice_vals

    def action_confirm(self):
        if self.need_authorize and self.is_authorize == False:
            return
        super(SaleOrder, self).action_confirm()

    def action_approve(self):
        super(SaleOrder, self).action_confirm()
        is_authorize = True
        return True


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    weight = fields.Float(string='Weight KG', store=True)
    total_weight = fields.Float(string="Total Weight KG", readonly=True, compute="_compute_total_weight")
    rack_qty = fields.Integer(string="Rack Qty", default=0, readonly=True, compute="_compute_total_weight")

    @api.onchange('product_id')
    def onchange_weight(self):
        for line in self:
            if not line.product_id == False and not line.product_id.weight == False:
                line.weight = line.product_id.weight
    
    @api.depends('product_uom_qty', 'weight')
    def _compute_total_weight(self):
        for line in self:
            line.total_weight = line.weight * line.product_uom_qty
            rack = 1
            if line.product_id and line.product_id.rack_qty > 0:
                rack = line.product_id.rack_qty
            line.rack_qty = math.ceil(line.product_uom_qty / rack)
