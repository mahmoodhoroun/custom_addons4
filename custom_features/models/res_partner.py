from odoo import models, fields, api

class PartnerInherit(models.Model):
    _inherit = 'res.partner'


    @api.model
    def create(self, vals):
        # Set the default language to 'fr_FR' if not provided
        vals['lang'] = 'fr_FR'
        return super(PartnerInherit, self).create(vals)