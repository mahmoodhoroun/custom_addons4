from odoo import models, fields, api

class ResUsers(models.Model):
    _inherit = 'res.users'
    
    signature_image = fields.Binary(string="Signature Image", attachment=True, help="Upload your signature image here", copy=False)
    stamp_image = fields.Binary(string="Stamp Image", attachment=True, help="Upload your stamp image here", copy=False)
