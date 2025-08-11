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
                # Send WhatsApp message using Chronodiali template for heavy packages
                self._send_delivery_whatsapp_message('chronodiali')
            else:
                self.call_shipping_api()
                # Send WhatsApp message using Cathedis template for light packages
                self._send_delivery_whatsapp_message('cathedis')
    
    def _send_delivery_whatsapp_message(self, template_type):
        """
        Send WhatsApp message to customer when delivery shipping is created.
        
        Args:
            template_type (str): Either 'cathedis' or 'chronodiali' to determine which template to use
        """
        try:
            # Determine which template to use based on template_type
            if template_type == 'chronodiali':
                config_param = 'custom_features.chronodiali_whatsapp_template'
                template_name = 'Chronodiali'
            else:  # cathedis
                config_param = 'custom_features.cathedis_whatsapp_template'
                template_name = 'Cathedis'
            
            # Get the WhatsApp template from settings
            template_id = int(self.env['ir.config_parameter'].sudo().get_param(config_param) or 0)
            
            if not template_id:
                _logger.info("No %s WhatsApp template configured in settings", template_name)
                return
            
            template = self.env['whatsapp.template'].browse(template_id)
            if not template.exists():
                _logger.warning("Configured %s WhatsApp template (ID: %s) does not exist", template_name, template_id)
                return
            
            # Check if customer has a phone number
            phone_number = self.partner_id.mobile or self.partner_id.phone
            if not phone_number:
                _logger.info("Customer %s has no phone number, skipping WhatsApp message", self.partner_id.name)
                return
            
            # Create WhatsApp composer to send the message
            composer = self.env['whatsapp.composer'].create({
                'res_model': 'stock.picking',
                'res_ids': str([self.id]),
                'wa_template_id': template.id,
                'phone': phone_number,
            })
            
            # Send the message
            composer._send_whatsapp_template()
            _logger.info("%s WhatsApp delivery message sent to customer %s for picking %s", 
                        template_name, self.partner_id.name, self.name)
            
        except Exception as e:
            _logger.error("Failed to send %s WhatsApp delivery message for picking %s: %s", 
                         template_name, self.name, str(e))
