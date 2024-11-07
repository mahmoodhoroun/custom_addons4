from odoo import fields, models


class Picking(models.Model):
    _inherit = "stock.picking"

    # Added new field #T7157
    # Added copy false. #T7254
    return_reason = fields.Html(copy=False)
