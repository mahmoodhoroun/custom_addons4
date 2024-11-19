from odoo import _, api, fields, models
import logging

class Picking(models.Model):
    _inherit = 'stock.picking'
    sale_id = fields.Many2one('sale.order', string="Sale Order", ondelete='cascade')

    # def _create_returns(self):
    #     result = super(ReturnPicking, self)._create_returns()

    #     self.picking_id.state = 'draft'
    #     order = self.picking_id.origin
    #     logging.error("*****************************************")
    #     logging.error(order)
        
    #     SaleOrder = self.env['sale.order']
    #     sale_order = SaleOrder.search([('name', '=', order)], limit=1)
    #     # sale_order.action_cancel()
    #     if sale_order:
    #         logging.info("Sale Order found: %s", sale_order.id)

    #         sale_order._action_cancel()
    #         logging.info("Sale Order %s has been cancelled.", sale_order.id)
    #     else:
    #         logging.warning("No Sale Order found with name: %s", order)
            
    #     return result


    def button_validate(self):
        result = super(Picking, self).button_validate()
        
        if self.picking_type_id.code == 'incoming':
            order = self.group_id.name
            logging.error("*****************************************")
            logging.error(order)
            logging.error(self.group_id.name)
            
            
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

