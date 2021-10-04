from odoo import api, fields, models, _


class AccountMove(models.Model):
    _inherit = "account.move"

    # Field declaration
    last_invoiced_date = fields.Datetime(string='Last Invoice date', readonly=True)
