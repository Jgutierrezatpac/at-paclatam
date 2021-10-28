from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _


class RentalWizard(models.TransientModel):
    _inherit = 'rental.wizard'

    # Fields declarations
    pickup_date = fields.Datetime(default=lambda x: fields.Datetime.now())
    return_date = fields.Datetime(default=lambda x: fields.Datetime.now() + relativedelta(months=1))
