import requests
import json
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class ShipsyConnector(models.Model):
    _name = 'shipping.shipsy.connector'
    _description = 'Shipsy API Connector'

    name = fields.Char(string='Name', required=True)
    api_url = fields.Char(string='API URL', required=True)
    api_key = fields.Char(string='API Key', required=True)
    customer_code = fields.Char(string='Customer Code', help='Customer code used for Shipsy API requests')
    active = fields.Boolean(default=True)

    def test_connection(self):
        """Test the connection to Shipsy API"""
        self.ensure_one()
        try:
            # Prepare headers with API key
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.api_key}'
            }
            
            # Make a simple request to test the connection
            # This URL should be adjusted based on Shipsy's actual API endpoint for testing
            test_url = f"{self.api_url}/ping"
            
            response = requests.get(test_url, headers=headers)
            
            if response.status_code in [200, 201]:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Connection Test Successful'),
                        'message': _('Successfully connected to Shipsy API.'),
                        'sticky': False,
                        'type': 'success',
                        'next': {
                            'type': 'ir.actions.act_window',
                            'res_model': 'shipping.shipsy.connector',
                            'res_id': self.id,
                            'view_mode': 'form',
                            'target': 'current',
                            'views': [(False, 'form')],
                        }
                    }
                }
            else:
                raise UserError(_('Failed to connect to Shipsy API: %s') % response.text)
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection Test Failed'),
                    'message': str(e),
                    'sticky': False,
                    'type': 'danger',
                }
            }
