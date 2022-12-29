# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, _

class MessageWizard(models.TransientModel):
    _name = 'message.wizard'
    _description = 'success message wizard'

    message = fields.Text('Message', required=True,readonly=True)

    def action_ok(self):
        """ close wizard"""
        return {'type': 'ir.actions.act_window_close'}