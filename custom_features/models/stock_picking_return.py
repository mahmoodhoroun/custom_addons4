from odoo import _, api, fields, models
import logging

class ReturnPicking(models.TransientModel):
    _inherit = 'stock.return.picking'


    def _create_returns(self):
        result = super(ReturnPicking, self)._create_returns()


        order = self.picking_id.origin
        logging.error("*****************************************")
        logging.error(order)
        
        SaleOrder = self.env['sale.order']
        sale_order = SaleOrder.search([('name', '=', order)], limit=1)
        # sale_order.action_cancel()
        if sale_order:
            logging.info("Sale Order found: %s", sale_order.id)

            sale_order._action_cancel()
            logging.info("Sale Order %s has been cancelled.", sale_order.id)
        else:
            logging.warning("No Sale Order found with name: %s", order)
            
        return result