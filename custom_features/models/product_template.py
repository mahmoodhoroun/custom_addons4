from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    separate_delivery_per_unit = fields.Boolean(
        string='Separate Delivery Per Unit',
        help='When enabled, each unit of this product will be delivered separately when confirming a sale order.'
    )
