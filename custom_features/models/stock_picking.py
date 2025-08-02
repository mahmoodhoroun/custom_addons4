from odoo import models, fields, api, _
import logging
_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = 'stock.picking'
    
    is_label_printed = fields.Boolean(string='Étiquette de prélèvement', default=False, 
                                     help="Indicates if the picking label has been printed")
    expedie = fields.Boolean(string='Expedié', default=False, 
                                     help="Indicates if the picking has been expedited", compute='_compute_expedie')
    ramasse = fields.Boolean(string='Ramassé', default=False, 
                                     help="Indicates if the picking has been ramassed", compute='_compute_ramasse')
    customer_phone = fields.Char(string='Customer Phone', compute='_compute_customer_phone')
    
    def _compute_customer_phone(self):
        for picking in self:
            picking.customer_phone = picking.partner_id.phone
    
    def _compute_expedie(self):
        for picking in self:
            if picking.delivery_id or picking.shipsy_reference_number:
                picking.expedie = True
            else:
                picking.expedie = False

    def _compute_ramasse(self):
        for picking in self:
            if picking.new_state == 'delivery_pickup' or picking.shipsy_pickup_id:
                picking.ramasse = True
            else:
                picking.ramasse = False

    def create_delivery_shipping(self):
        for picking in self:
            weight = 0
            for line in picking.move_ids:
                weight += line.product_id.weight * line.product_uom_qty

            if weight >= 5:
                self.action_send_to_shipsy()
            else:
                self.call_shipping_api()
