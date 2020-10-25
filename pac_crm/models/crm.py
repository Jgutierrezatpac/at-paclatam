# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class CrmLead(models.Model):
    _inherit = 'crm.lead'

    num_months = fields.Integer(string='Number of Months', default=0)
    second_team_id = fields.Many2one('second.sales.team', string="Second Sales Team")
    rental_probability = fields.Float(string='Rental Probability')
    used_probability = fields.Float(string='Used Probability')
    used_sale_value = fields.Float(string="Used Sale Deal Value", store=True, compute="_compute_value")
    sale_value = fields.Float(string="Sale Deal Value", store=True, compute="_compute_value")
    rental_value = fields.Float(string="Rental Deal Value", store=True,compute="_compute_value")
    rental_weight = fields.Float(string="Rental weight", store=True, compute="_compute_selected_quotation")
    sales_weight = fields.Float(string="Sales weight", store=True, compute="_compute_selected_quotation")

    # For Leads only start
    lead_weight = fields.Float(string="Weight (Appr.)")
    lead_sale_value = fields.Float(string="New Sale Deal Value (Appr.)", compute="_compute_leads_value")
    lead_usedsale_value = fields.Float(string="Used Sale Deal Value (Appr.)", compute="_compute_leads_value")
    lead_rental_value = fields.Float(string="Rental Deal Value (Appr.)", compute="_compute_leads_value")

    sales_new_rate = fields.Float(string="Sales New Rate")
    sales_old_rate = fields.Float(string="Sales Used Rate")
    rental_rate = fields.Float(string="Rental Rate")
    # end

    rental_order_count = fields.Integer(string="Rental order count", compute="_compute_rental_total",default=0)
    rental_amount_total = fields.Monetary(compute='_compute_rental_total', string="Sum of Rentals", default=0.0, currency_field='company_currency')
    rent_quotation_count = fields.Integer(compute='_compute_rental_total', string="Number of Rentals", default=0)

    total_selected_sales = fields.Monetary(string="Total selected Sales", currency_field='company_currency', compute="_compute_selected_quotation")
    total_selected_rental = fields.Monetary(string="Total selected Rental", currency_field='company_currency', compute="_compute_selected_quotation")
    total_selected_used = fields.Monetary(string="Total selected Used Sales", currency_field='company_currency', compute="_compute_selected_quotation")

    @api.depends('num_months','lead_weight','sales_new_rate', 'sales_old_rate', 'rental_rate', 'probability', 'rental_probability', 'used_probability')
    def _compute_leads_value(self):
        for lead in self:
            lead.lead_sale_value = lead.lead_weight * lead.sales_new_rate * (lead.probability / 100.0)
            lead.lead_usedsale_value = lead.lead_weight * lead.sales_old_rate * (lead.used_probability / 100.0)
            lead.lead_rental_value = lead.lead_weight * lead.rental_rate * (lead.rental_probability / 100.0)* lead.num_months

    def _compute_selected_quotation(self):
        for lead in self:
            rental = sales = used = 0.0
            rental_weight = sales_weight = 0
            for order in lead.order_ids:
                if order.state in ('draft', 'sent') and order.is_rental_order == True and order.is_select == True:
                    rental += order.amount_untaxed
                    rental_weight += order.total_weight
                elif order.state in ('draft', 'sent') and order.is_select == True:
                    if order.is_used:
                        used += order.amount_untaxed
                    else: 
                        sales += order.amount_untaxed
                    sales_weight += order.total_weight
            lead.total_selected_sales = sales 
            lead.total_selected_rental = rental
            lead.total_selected_used = used
            lead.rental_weight = rental_weight
            lead.sales_weight = sales_weight

    @api.depends('order_ids.state', 'order_ids.currency_id', 'order_ids.amount_untaxed', 'order_ids.date_order', 'order_ids.company_id')
    def _compute_rental_total(self):
        for lead in self:
            total = 0.0
            quotation_cnt = 0
            rental_order_cnt = 0
            company_currency = lead.company_currency or self.env.company.currency_id
            for order in lead.order_ids:
                if order.state in ('draft', 'sent') and order.is_rental_order == True:
                    quotation_cnt += 1
                if order.state not in ('draft', 'sent', 'cancel') and order.is_rental_order == True:
                    rental_order_cnt += 1
                    total += order.currency_id._convert(
                        order.amount_untaxed, company_currency, order.company_id, order.date_order or fields.Date.today())
            lead.rental_amount_total = total
            lead.rent_quotation_count = quotation_cnt
            lead.rental_order_count = rental_order_cnt
            lead._compute_value()
    
    @api.depends('order_ids.state', 'order_ids.currency_id', 'order_ids.amount_untaxed', 'order_ids.date_order', 'order_ids.company_id')
    def _compute_sale_data(self):
        super(CrmLead,self)._compute_sale_data()
        for lead in self:
            lead.sale_amount_total -= lead.rental_amount_total
            lead.quotation_count -= lead.rent_quotation_count
            lead.sale_order_count -= lead.rental_order_count

    @api.depends('num_months','rental_probability', 'probability','total_selected_sales','total_selected_rental')
    def _compute_value(self):
        for lead in self:
            lead.used_sale_value = lead.total_selected_used * (lead.used_probability / 100.00)
            lead.sale_value = lead.total_selected_sales * (lead.probability / 100.00)
            lead.rental_value = lead.total_selected_rental * lead.num_months * (lead.rental_probability / 100.00)

    # create new rental quotation
    def action_rental_quotations_new(self):
        action = self.action_sale_quotations_new()
        action['context']['default_is_rental_order'] = True
        return action
    
 
    # stat button and filters for the sale order
    def action_view_sale_quotation(self):
        action = super(CrmLead,self).action_view_sale_quotation()
        action['domain'] = [('opportunity_id', '=', self.id), ('state', 'in', ['draft', 'sent']),('is_rental_order','=',False)]
        return action

    def action_view_sale_order(self):
        action = super(CrmLead,self).action_view_sale_order()
        action['domain'] = [('opportunity_id', '=', self.id), ('state', 'not in', ('draft', 'sent', 'cancel')),('is_rental_order','=',False)]
        return action

    def action_view_rental_quotation(self):
        action = self.env.ref('sale_renting.rental_order_action').read()[0]
        action['context'] = {
            'search_default_draft': 1,
            'search_default_partner_id': self.partner_id.id,
            'default_partner_id': self.partner_id.id,
            'default_opportunity_id': self.id,
            'default_is_rental_order': True,
            'default_rent_ok': 1,
            'rental_products': True,
        }
        action['domain'] = [('opportunity_id', '=', self.id), ('state', 'in', ['draft', 'sent']),('is_rental_order','=',True)]
        quotations = self.mapped('order_ids').filtered(lambda l: l.state in ('draft', 'sent') and l.is_rental_order == True)
        if len(quotations) == 1:
            action['views'] = [(self.env.ref('sale_renting.rental_order_primary_form_view').id, 'form')]
            action['res_id'] = quotations.id
        return action
        # action['domain'] = [('opportunity_id', '=', self.id), ('state', 'in', ['draft', 'sent']),('is_rental_order','=',True)]
        # return action

    def action_view_rental_order(self):
        action = self.env.ref('sale_renting.rental_order_action').read()[0]
        action['context'] = {
            'search_default_partner_id': self.partner_id.id,
            'default_partner_id': self.partner_id.id,
            'default_opportunity_id': self.id,
            'default_is_rental_order': True,
            'default_rent_ok': 1,
            'rental_products': True,
        }
        action['domain'] = [('opportunity_id', '=', self.id), ('state', 'not in', ('draft', 'sent', 'cancel')),('is_rental_order','=',True)]
        orders = self.mapped('order_ids').filtered(lambda l: l.state not in ('draft', 'sent', 'cancel') and l.is_rental_order == True)
        if len(orders) == 1:
            action['views'] = [(self.env.ref('sale_renting.rental_order_primary_form_view').id, 'form')]
            action['res_id'] = orders.id
        return action
        # action['domain'] = [('opportunity_id', '=', self.id), ('state', 'not in', ('draft', 'sent', 'cancel')),('is_rental_order','=',True)]
        # return action

class SecondTeam(models.Model):
    _name = "second.sales.team"
    _description = "Second Sales Team"

    name = fields.Char('Sales Team', required=True, translate=True)
    sequence = fields.Integer('Sequence', default=10)
    active = fields.Boolean(default=True, help="If the active field is set to false, it will allow you to hide the Sales Team without removing it.")
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one(
        "res.currency", related='company_id.currency_id',
        string="Currency", readonly=True)
    user_id = fields.Many2one('res.users', string='Team Leader', check_company=True)
    member_ids = fields.One2many(
        'res.users', 'sale_team_id', string='Channel Members', check_company=True,
        domain=lambda self: [('groups_id', 'in', self.env.ref('base.group_user').id)],
        help="Add members to automatically assign their documents to this sales team. You can only be member of one team.")