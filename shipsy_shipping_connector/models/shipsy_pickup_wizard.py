from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import json
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)

class ShipsyPickupWizard(models.TransientModel):
    _name = 'shipsy.pickup.wizard'
    _description = 'Chronodiali Pickup Request Wizard'
    
    pickup_date = fields.Date(string='Pickup Date', required=True, default=fields.Date.context_today)
    time_slot = fields.Selection([
        ('09:00-12:00', '09:00 - 12:00'),
        ('12:00-15:00', '12:00 - 15:00'),
        ('15:00-18:00', '15:00 - 18:00'),
        ('18:00-21:00', '18:00 - 21:00'),
    ], string='Pickup Time Slot', required=True, default='09:00-12:00')
    shipsy_connector_id = fields.Many2one('shipping.shipsy.connector', string='Chronodiali Connector', 
                                         required=True, default=lambda self: self._get_default_shipsy_connector())
    
    def _get_default_shipsy_connector(self):
        """Get the first active Shipsy connector"""
        connector = self.env['shipping.shipsy.connector'].search([('active', '=', True)], limit=1)
        return connector.id if connector else False
    
    def _get_time_slot_times(self):
        """Get start and end times from the selected time slot"""
        if not self.time_slot:
            return '09:00', '12:00'  # Default values
            
        start_time, end_time = self.time_slot.split('-')
        return start_time, end_time
    
    def _format_date(self, date_obj):
        """Format date as DD/MM/YYYY without quotes"""
        # Format as DD/MM/YYYY without quotes
        return date_obj.strftime('%d/%m/%Y')
    
    def action_create_pickup(self):
        """Create pickup request in Shipsy"""
        # Get selected pickings
        active_ids = self.env.context.get('active_ids', [])
        if not active_ids:
            raise UserError(_("No deliveries selected for pickup."))
            
        pickings = self.env['stock.picking'].browse(active_ids)
        _logger.info(f"Chronodiali Pickup - Selected pickings: {pickings}")
        _logger.info(f"************************************************")
        # Calculate total items and weight
        total_items = len(pickings)
        _logger.info(f"Chronodiali Pickup - Total items: {total_items}")
        total_weight = sum(
            sum(move_line.product_id.weight * move_line.quantity for move_line in picking.move_line_ids)
            for picking in pickings
        )
        
        # Get company details for pickup address
        company = self.env.company
        
        # Extract API key from JSON if needed
        api_key = self.shipsy_connector_id.api_key
        try:
            # Check if the API key is stored as JSON
            if api_key.startswith('[{') and 'value' in api_key:
                # Parse the JSON string
                api_key_json = json.loads(api_key)
                # Extract the actual API key value
                for item in api_key_json:
                    if item.get('key') == 'api-key' and item.get('enabled'):
                        api_key = item.get('value')
                        break
        except Exception as e:
            _logger.warning(f"Error parsing API key: {str(e)}")
        
        # Prepare payload
        payload = {
            "pickup_type": "BUSINESS",
            "customer_code": "",
            "pickup_address": {
                "name": company.name,
                "phone": company.phone or "",
                "address_line_1": company.street or "",
                "address_line_2": company.street2 or "",
                "pincode": company.zip or "",
                "city": company.city or "",
                "country": company.country_id.name if company.country_id else ""
            },
            "load_type": "NON-DOCUMENT",
            "total_items": str(total_items),
            "total_weight": str(total_weight),
            "pickup_slot": {
                "start": self._get_time_slot_times()[0],
                # "end": self._get_time_slot_times()[1],
                "date": self._format_date(self.pickup_date)
            }
        }

        start_time, end_time = self._get_time_slot_times()
        _logger.info(f"Shipsy time slot - start time: {start_time}")
        _logger.info(f"Shipsy time slot - end time: {end_time}")
        
        try:
            # API endpoint
            url = f"{self.shipsy_connector_id.api_url}/api/customer/integration/pickup/create"
            
            # Headers
            headers = {
                'accept': 'application/json',
                'api-key': api_key,
                'content-type': 'application/json'
            }
            
            _logger.info(f"Shipsy Pickup API request: {url}")
            _logger.info(f"Shipsy Pickup API payload: {payload}")
            
            # Send request
            response = requests.post(url, headers=headers, data=json.dumps(payload))
            
            # Process response
            if response.status_code in [200, 201]:
                result = response.json()
                _logger.info(f"Shipsy Pickup API response: {result}")
                
                if result.get('status') == 'OK' and result.get('data', {}).get('pickupId'):
                    pickup_id = result['data']['pickupId']
                    
                    # Create a message in the chatter for each picking and save pickup ID
                    for picking in pickings:
                        start_time, end_time = self._get_time_slot_times()
                        # Save pickup ID to the picking
                        picking.write({
                            'shipsy_pickup_id': pickup_id
                        })
                        
                        # Post message in chatter
                        picking.message_post(
                            body=_(f"Pickup request created in Shipsy with ID: {pickup_id}<br/>"
                                  f"Pickup Date: {self.pickup_date}<br/>"
                                  f"Pickup Time: {start_time} - {end_time}")
                        )
                    
                    # Show success notification and close the wizard
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Success'),
                            'message': _('Pickup request successfully created in Shipsy with ID: %s') % pickup_id,
                            'sticky': False,
                            'type': 'success',
                            'next': {
                                'type': 'ir.actions.act_window_close'
                            }
                        }
                    }
                else:
                    failure_reason = result.get('data', {}).get('failureReason', 'Unknown error')
                    raise UserError(_('Error in Shipsy API response: %s') % failure_reason)
            else:
                raise UserError(_('Failed to connect to Shipsy API: %s') % response.text)
                
        except Exception as e:
            _logger.error('Shipsy API error: %s', str(e))
            raise UserError(_('Error connecting to Shipsy API: %s') % str(e))
