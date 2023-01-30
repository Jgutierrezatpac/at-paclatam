from odoo import fields, api, models, _


class ResPartner(models.Model):
    _inherit = "res.partner"

    # Field declarations.
    type = fields.Selection(selection_add=[('rental', 'Rental Address')])
    rental_location_id = fields.Many2one('stock.location', string="Rental Location")

    # Inherited methods
    @api.model
    def create(self, values):
        res = super(ResPartner, self).create(values)
        rental_location = self.env.ref('rental_billing_pac.stock_location_rental',
                                       raise_if_not_found=True)
        if not values.get('parent_id'):
            new_location = self.env['stock.location'].create({
                'name': values.get('name'),
                'usage': 'customer',
                'location_id': rental_location.id,
            })
            res.update({'rental_location_id': new_location.id})
        else:
            if values.get('type') == 'rental':
                domain = [('id', '=', values.get('parent_id'))]
                fields = ['rental_location_id']
                data = self.search_read(domain=domain, fields=fields)
                if data[0].get('rental_location_id'):
                    rental_location = self.env['stock.location'].create({
                        'name': values.get('name'),
                        'usage': 'customer',
                        'location_id': data[0].get('rental_location_id')[0]
                    })
                    res.update({'rental_location_id': rental_location.id})
                else:
                    parent_new_location = self.env['stock.location'].create({
                        'name': res.parent_id.name,
                        'usage': 'customer',
                        'location_id': rental_location.id,
                    })
                    res.parent_id.update({'rental_location_id': parent_new_location.id})
                    child_rental_location = self.env['stock.location'].create({
                        'name': values.get('name'),
                        'usage': 'customer',
                        'location_id': parent_new_location.id,
                    })
                    res.update({'rental_location_id': child_rental_location.id})
        return res
