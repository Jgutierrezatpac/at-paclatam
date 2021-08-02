# -- coding: utf-8 --
{
    'name': 'At-Pac CRM',

    'summary': 'At-Pac CRM customization',

    'description': """
    task id: 2314441
    At-Pac Bolivia : CRM customizations
    """,
    'author': 'Odoo',
    'website': 'https://www.odoo.com/',

    'category': 'Custom Development',
    'version': '1.0',
    'license': 'OEEL-1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'sales_team','crm','sale','sale_crm', 'sale_renting'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'data/data.xml',
        'views/crm_form_inherit.xml',
        'views/sale_discount_form.xml',
        'views/sale_order_form_inherit.xml',
        'views/account_move_form_inherit.xml',
        'views/users_form_inherit.xml',
        'views/second_team_views.xml',
        'views/product_inherit_form.xml',
        'views/partner_inherit_form.xml',
        'wizard/success_message.xml'
    ],
    # only loaded in demonstration mode
    'demo': [],
    'application': False,
}
