# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class CrmLead(models.Model):
    _inherit = 'crm.lead'

    num_months = fields.Integer(string='Number of Months', default=0)
    second_team_id = fields.Many2one('second.sales.team', string="Second Sales Team")
    probability = fields.Float(string='New Sale Probability')
    rental_probability = fields.Float(string='Rental Probability')
    used_probability = fields.Float(string='Used Sale Probability')
    used_sale_value = fields.Float(string="Used Sale Deal Value", store=True, compute="_compute_value")
    prorated_revenue = fields.Float(string="New Sale Deal Value", store=True, compute="_compute_value")
    rental_value = fields.Float(string="Rental Deal Value", store=True,compute="_compute_value")

    rental_weight = fields.Float(string="Rental weight", store=True, default=0)
    sales_weight = fields.Float(string="New Sales weight", store=True, default=0)
    used_sales_weight = fields.Float(string="Used Sales weight", store=True, default=0)

    total_selected_sales = fields.Monetary(string="Sales New Rate", currency_field='company_currency', default=0)
    total_selected_rental = fields.Monetary(string="Rental Rate", currency_field='company_currency', default=0)
    total_selected_used = fields.Monetary(string="Sales Used Rate", currency_field='company_currency', default=0)

    expected_revenue = fields.Monetary('New Sale Expected Revenue', currency_field='company_currency', tracking=True, )
    used_planned_revenue = fields.Monetary('Used Sale Expected Revenue', currency_field='company_currency', tracking=True, )
    rental_planned_revenue = fields.Monetary('Rental Expected Revenue', currency_field='company_currency', tracking=True, )
    is_order_calc = fields.Boolean(string='CRM contains orders', default=False, compute='_compute_crm')
    
    def _compute_crm(self):
        for crm in self:
            if len(crm.mapped('order_ids').filtered(lambda l: l.state in ('draft', 'sent') and l.is_select)) > 0:
                crm.is_order_calc = True
            else:
                crm.is_order_calc = False

    @api.onchange('quotation_count', 'rental_quotation_count', 'order_ids','num_months')
    def _compute_selected_quotation(self):
        for lead in self:
            rental = lead.total_selected_rental * lead.rental_weight * lead.num_months
            sales = lead.total_selected_sales * lead.sales_weight
            used = lead.total_selected_used * lead.used_sales_weight
            rental_weight = lead.rental_weight
            sales_weight = lead.sales_weight
            used_sales_weight = lead.used_sales_weight
            
            if lead.is_order_calc:
                rental = sales = used = 0.0
                rental_weight = sales_weight = used_sales_weight = 0
                for order in lead.order_ids:
                    if order.state in ('draft', 'sent') and order.is_rental_order and order.is_select:
                        rental += order.amount_untaxed
                        rental_weight += order.total_weight
                    elif order.state in ('draft', 'sent') and order.is_select:
                        if order.is_used:
                            used += order.amount_untaxed
                            used_sales_weight += order.total_weight
                        else: 
                            sales += order.amount_untaxed
                            sales_weight += order.total_weight
                rental *= lead.num_months

            lead.expected_revenue = sales
            lead.rental_planned_revenue = rental
            lead.used_planned_revenue = used
            lead.rental_weight = rental_weight
            lead.sales_weight = sales_weight
            lead.used_sales_weight = used_sales_weight

    def _compute_rental_count(self):
        super()._compute_rental_count()
        for lead in self:
            lead._compute_value()
    
    @api.depends('order_ids.state', 'order_ids.currency_id', 'order_ids.amount_untaxed', 'order_ids.date_order', 'order_ids.company_id')
    def _compute_sale_data(self):
        super()._compute_sale_data()
        for lead in self:
            lead.sale_amount_total -= lead.rental_amount_total
            lead.quotation_count -= lead.rental_quotation_count
            lead.sale_order_count -= lead.rental_order_count

    @api.depends('num_months','rental_probability', 'probability','expected_revenue','rental_planned_revenue','used_planned_revenue')
    def _compute_value(self):
        self._compute_selected_quotation()
        for lead in self:
            if not lead.is_order_calc:
                lead.prorated_revenue = lead.expected_revenue * (lead.probability / 100.0)
                lead.used_sale_value = lead.used_planned_revenue * (lead.used_probability / 100.0)
                lead.rental_value = lead.rental_planned_revenue * (lead.rental_probability / 100.0)
            else:
                lead.used_sale_value = lead.used_planned_revenue * (lead.used_probability / 100.00)
                lead.prorated_revenue = lead.expected_revenue * (lead.probability / 100.00)
                lead.rental_value = lead.rental_planned_revenue *  (lead.rental_probability / 100.00)
                lead._compute_rate_per_weight()
        
    @api.depends('expected_revenue','rental_planned_revenue','used_planned_revenue','rental_weight','sales_weight')
    def _compute_rate_per_weight(self):
        if self.rental_weight > 0:
            self.total_selected_rental = (self.rental_planned_revenue / self.rental_weight * 1000)
            if self.is_order_calc and self.num_months > 0:
                self.total_selected_rental = self.total_selected_rental / self.num_months
        else:
            self.total_selected_rental = 0

        if self.sales_weight > 0:
            self.total_selected_sales = self.expected_revenue / self.sales_weight * 1000
        else:
            self.total_selected_sales = 0

        if self.used_sales_weight > 0:
            self.total_selected_used = self.used_planned_revenue / self.used_sales_weight * 1000
        else:
            self.total_selected_used = 0

    # stat button and filters for the sale order
    def action_view_sale_quotation(self):
        action = super().action_view_sale_quotation()
        action['domain'] = [('opportunity_id', '=', self.id), ('state', 'in', ['draft', 'sent']),('is_rental_order','=',False)]
        return action

    def action_view_sale_order(self):
        action = super().action_view_sale_order()
        action['domain'] = [('opportunity_id', '=', self.id), ('state', 'not in', ('draft', 'sent', 'cancel')),('is_rental_order','=',False)]
        return action

    def action_view_rental_order(self):
        action = self.env.ref("ir.actions.actions")._for_xml_id("sale_renting.rental_order_action")
        action['context'] = {
            'search_default_partner_id': self.partner_id.id,
            'default_partner_id': self.partner_id.id,
            'default_opportunity_id': self.id,
            'default_is_rental_order': True,
            'default_rent_ok': 1,
            'rental_products': True,
        }
        action['domain'] = [('opportunity_id', '=', self.id), ('state', 'not in', ('draft', 'sent', 'cancel')),('is_rental_order','=',True)]
        orders = self.mapped('order_ids').filtered(lambda l: l.state not in ('draft', 'sent', 'cancel') and l.is_rental_order)
        if len(orders) == 1:
            action['views'] = [(self.env.ref('sale_renting.rental_order_primary_form_view').id, 'form')]
            action['res_id'] = orders.id
        return action

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