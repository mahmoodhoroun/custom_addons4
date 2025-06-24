from odoo import models, fields, api, _

class StockPicking(models.Model):
    _inherit = 'stock.picking'
    
    is_label_printed = fields.Boolean(string='Étiquette de prélèvement', default=False, 
                                     help="Indicates if the picking label has been printed")
