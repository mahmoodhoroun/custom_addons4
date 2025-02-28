
from odoo import models, fields, api

class ResPartner(models.Model):
    _inherit = 'res.partner'

    rc = fields.Char(string='R.C.')
    tp = fields.Char(string='T.P.')
    iff = fields.Char(string='I.F.')
    cnss = fields.Char(string='C.N.S.S.')
    ice = fields.Char(string='I.C.E.')
    capital = fields.Char(string='Capital')
    cin = fields.Char(string='CIN')
    
   
        

class ResCompany(models.Model):
    _inherit = 'res.company'

    rc = fields.Char(string='R.C.')
    tp = fields.Char(string='T.P.')
    iff = fields.Char(string='I.F.')
    cnss = fields.Char(string='C.N.S.S.')
    ice = fields.Char(string='I.C.E.')
    capital = fields.Char(string='Capital')

