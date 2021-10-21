# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Rental Billing AtPac",

    'summary': """
        This is module for joining Rental app with stock and invoice.
    """,

    'description': """
        Task id:  2481715
        This is module for joining Rental app with stock and invoice.
    """,
    'author': 'Odoo Ps',
    'version': '1.0.0',

    'depends': ['sale_management', 'stock', 'contacts', 'sale_renting'],

    'data': [
        'security/ir.model.access.csv',
        'data/data.xml',
        'views/res_partner_views.xml',
        'views/sale_order_views.xml',
        'views/stock_picking_view.xml',
        'wizards/return_rental_wizard.xml',
        'wizards/sale_make_invoice_advance_view.xml',
    ],
    'installable': True,
}
