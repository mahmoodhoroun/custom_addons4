from odoo import models, fields, api, _
import logging
_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = 'stock.picking'
    
    is_label_printed = fields.Boolean(string='Étiquette de prélèvement', default=False, 
                                     help="Indicates if the picking label has been printed")

    def create_delivery_shipping(self):
        for picking in self:
            weight = 0
            for line in picking.move_ids:
                weight += line.product_id.weight * line.product_uom_qty

            if weight >= 5:
                self.action_send_to_shipsy()
            else:
                self.call_shipping_api()
