# -*- coding: utf-8 -*-


from odoo import api, fields, models, _, SUPERUSER_ID
import base64
import xlrd
from odoo.exceptions import UserError
from odoo.tools import float_round
import math

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    discount_ids = fields.Many2many("discount.sale",'order_discount', string="Discounts", store=True)
    replace_discount_ids = fields.Many2many("discount.sale","replacement_discount", string="Replacement Discounts", store=True)

    need_authorize = fields.Boolean(string="Discount superior authorization",store=True,compute="_compute_authorization")
    is_authorize = fields.Boolean(string="Authorization",store=True, )
    amount_discount = fields.Monetary(string='Discount Total', store=True, compute='_amount_all')

    is_select = fields.Boolean(string="CRM Calculate Selection")
    is_used = fields.Boolean(string="Sales(Used) Quotation")

    file_name = fields.Char(string='File Name')
    file_data = fields.Binary('import file', )

    total_weight = fields.Float(string="Total Weight", compute="_compute_total_weight_parts")
    total_part = fields.Integer(string="Total Parts", compute="_compute_total_weight_parts")

    replacement_price = fields.Monetary(string='Replacement', store=True, compute='_compute_total_weight_parts') 

    @api.depends('order_line')
    def _compute_total_weight_parts(self):
        for order in self:
            weight = parts = replacement = 0
            for line in order.order_line:
                weight += line.total_weight 
                parts += line.product_uom_qty
                replacement += line.replacement_total
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

        racks = {}

        for line in archive_lines:
            code = str(line.get('codigo_producto',"")).strip()
            product_id = self.env['product.product'].search([('default_code','=',code)])
            quantity = line.get(u'cantidad',0)

            racks_qty = 1
            if product_id.rack_qty > 0:
                racks_qty = quantity / product_id.rack_qty
            if product_id.rack_name and racks.get(product_id.rack_name):
                racks[product_id.rack_name] += racks_qty 
            elif product_id.rack_name:
                racks[product_id.rack_name] = racks_qty

            if not self.is_rental_order:
                if self and product_id:
                    vals = {
                        'order_id': self.id,
                        'product_id': product_id.id,
                        'product_uom_qty': float(quantity),
                        'product_uom': product_id.product_tmpl_id.uom_po_id.id,
                        'name': product_id.name,
                        'weight': product_id.weight,
                        'rack_qty': racks_qty,
                        'total_weight': product_id.weight * float(quantity)
                    }

            else:  
                if self and product_id:
                    price = 0
                    if product_id.rental_pricing_ids:
                        for pricing in product_id.rental_pricing_ids:
                            if pricing.unit == 'month':
                                price = pricing.price
                                break
                    vals = {
                        'order_id': self.id,
                        'product_id': product_id.id,
                        'product_uom_qty': float(quantity),
                        'price_unit' : price,
                        'replacement': product_id.lst_price,
                        'product_uom': product_id.product_tmpl_id.uom_po_id.id,
                        'name': product_id.name,
                        'weight': product_id.weight,
                        'rack_qty': racks_qty,
                        'total_weight': product_id.weight * float(quantity)
                    }
            self.env['sale.order.line'].create(vals)
        if not self.is_rental_order:
            for key in racks.keys():
                product_id = self.env['product.product'].search([('default_code','=',key)])
                if self and product_id:
                    vals = {
                        'order_id': self.id,
                        'product_id': product_id.id,
                        'product_uom_qty': math.ceil(racks[key]),
                        'price_unit': product_id.lst_price,
                        'product_uom': product_id.product_tmpl_id.uom_po_id.id,
                        'name': product_id.name,
                        'weight': product_id.weight,
                        'rack_qty' : 0,
                        'total_weight': product_id.weight * math.ceil(racks[key])
                    }
                self.env['sale.order.line'].create(vals)

        # use "racks" to create sale order.line for it
 
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
                'amount_total': amount_untaxed + amount_tax,
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

    weight = fields.Float(string='Weight KG', store=True, compute="_compute_weight")
    total_weight = fields.Float(string="Total Weight KG", readonly=True, compute="_compute_total_weight")
    rack_qty = fields.Float(string="Rack Qty", default=0, readonly=True, compute="_compute_total_weight")
    
    replacement = fields.Float(string="Replacement Cost", )
    discount_replace = fields.Float(string="Replacement Discount Cost", compute="_compute_prices")
    replacement_total = fields.Float(string="Replacement Subtotal", compute="_compute_replacement_total")
    unit_price_discount = fields.Float(string="Unit Price Discount", compute="_compute_prices")

    @api.depends('product_id', 'product_id.weight')
    def _compute_weight(self):
        for line in self:
            if line.product_id and line.product_id.weight:
                line.weight = line.product_id.weight
            else:
                line.weight = 0
            
    @api.depends('product_id','replacement','price_unit', 'order_id.discount_ids', 'order_id.replace_discount_ids')
    def _compute_prices(self):
        for line in self:
            sum_discounts = 0.0
            sum_replace = 0.0
            for dc in line.order_id.discount_ids:
                sum_discounts += dc.discount
            for dc in line.order_id.replace_discount_ids:
                sum_replace += dc.discount

            if line.product_id:
                line.discount_replace = (line.replacement * ((100 - sum_replace) / 100))
                line.unit_price_discount = (line.price_unit * ((100 - sum_discounts) / 100))
                line.replacement = line.product_id.lst_price
            else:
                line.discount_replace = 0
                line.unit_price_discount = 0
                line.replacement = 0

    @api.depends('product_id', 'discount_replace', 'product_uom_qty')
    def _compute_replacement_total(self):
        for line in self:
            if line.product_id:
                line.replacement_total = line.discount_replace * line.product_uom_qty
            else:
                line.replacement_total = 0

    @api.depends('product_uom_qty', 'weight')
    def _compute_total_weight(self):
        for line in self:
            line.total_weight = line.weight * line.product_uom_qty
            rack = 1
            if line.product_id:
                if line.product_id.rack_qty > 0:
                    rack = line.product_id.rack_qty  
            line.rack_qty = line.product_uom_qty / rack

    @api.depends('product_uom_qty', 'discount', 'unit_price_discount', 'tax_id')
    def _compute_amount(self):
        """
        Compute the amounts of the SO line.
        """
        for line in self:
            price = line.unit_price_discount * (1 - (line.discount or 0.0) / 100.0)
            taxes = line.tax_id.compute_all(price, line.order_id.currency_id, line.product_uom_qty, product=line.product_id, partner=line.order_id.partner_shipping_id)
            line.update({
                'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                'price_total': taxes['total_included'],
                'price_subtotal': taxes['total_excluded'],
            })
            if self.env.context.get('import_file', False) and not self.env.user.user_has_groups('account.group_account_manager'):
                line.tax_id.invalidate_cache(['invoice_repartition_line_ids'], [line.tax_id.id])