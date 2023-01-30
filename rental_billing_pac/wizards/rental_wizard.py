from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _


class RentalWizard(models.TransientModel):
    _inherit = 'rental.wizard'

    return_date = fields.Datetime(
        string="Return", required=True, help="Date of Return",
        default=lambda s: fields.Datetime.now() + relativedelta(months=1))
