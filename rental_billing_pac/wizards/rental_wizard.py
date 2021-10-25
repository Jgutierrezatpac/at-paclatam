from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _


class RentalWizard(models.TransientModel):
    _inherit = 'rental.wizard'

    # Fields declarations
    # return_date = fields.Datetime(default=lambda x: fields.Datetime.now() + relativedelta(months=1))
