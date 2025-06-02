import requests
import json
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class BaridMaConnector(models.Model):
    _name = 'shipping.barid.ma.connector'
    _description = 'Barid.ma API Connector'

    name = fields.Char(string='Name', required=True)
    username = fields.Char(string='Username', required=True)
    password = fields.Char(string='Password', required=True)
    api_url = fields.Char(string='API URL', default='https://client-apiecom.barid.ma/api')
    token = fields.Text(string='API Token', readonly=True)
    token_expiry = fields.Datetime(string='Token Expiry', readonly=True)
    active = fields.Boolean(default=True)
    id_contract1 = fields.Char(string='IdContract1')
    id_contract2 = fields.Char(string='IdContract2')
    id_deposit = fields.Char(string='IdDeposit')
    id_site = fields.Char(string='IdSite', readonly=True)
    codecontract1 = fields.Char(string='CodeContract1')
    secretkey1 = fields.Char(string='SecretKey1')
    codecontract2 = fields.Char(string='CodeContract2')
    secretkey2 = fields.Char(string='SecretKey2')

    
    def get_auth_token(self):
        """Get authentication token from Barid.ma API"""
        login_url = f"{self.api_url}/Account/login/{self.username}/password/{self.password}"
        
        try:
            headers = {
                'Content-Type': 'application/json'
            }
            
            response = requests.get(login_url, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('token'):
                    self.token = result['token']
                    # Token expiry could be extracted from the token if needed
                    return True
                else:
                    raise UserError(_('No token received from Barid.ma API'))
            else:
                raise UserError(_('Failed to authenticate with Barid.ma API: %s') % response.text)
                
        except Exception as e:
            _logger.error('Barid.ma API authentication error: %s', str(e))
            raise UserError(_('Error connecting to Barid.ma API: %s') % str(e))
    
    def test_connection(self):
        """Test the connection to Barid.ma API"""
        self.ensure_one()
        try:
            result = self.get_auth_token()
            if result:
                # Show notification and then reload
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Connection Test Successful'),
                        'message': _('Successfully connected to Barid.ma API.'),
                        'sticky': False,
                        'type': 'success',
                        'next': {
                            'type': 'ir.actions.act_window',
                            'res_model': 'shipping.barid.ma.connector',
                            'res_id': self.id,
                            'view_mode': 'form',
                            'target': 'current',
                            'views': [(False, 'form')],
                        }
                    }
                }
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
            
    def fetch_site_info(self):
        """Fetch site information from Barid.ma API"""
        self.ensure_one()
        
        # Ensure we have a valid token
        if not self.token:
            self.get_auth_token()
            
        # Prepare API URL
        url = f"{self.api_url}/SiteBam/dispostSites"
        
        # Prepare headers with token
        headers = {
            'Authorization': f'Bearer {self.token}'
        }
        
        try:
            # Make the API request
            response = requests.get(url, headers=headers)
            
            # Process the response
            if response.status_code == 200:
                sites = response.json()
                _logger.info(f"Barid.ma sites response: {sites}")
                
                if isinstance(sites, list) and sites:
                    # Get the first site's codeDivision
                    site_info = sites[0]
                    if site_info.get('codeDivision'):
                        self.id_site = site_info.get('codeDivision')
                        
                        # Show notification and then reload
                        return {
                            'type': 'ir.actions.client',
                            'tag': 'display_notification',
                            'params': {
                                'title': _('Site Information Updated'),
                                'message': _('Successfully fetched site information. Site code: %s') % self.id_site,
                                'sticky': False,
                                'type': 'success',
                                'next': {
                                    'type': 'ir.actions.act_window',
                                    'res_model': 'shipping.barid.ma.connector',
                                    'res_id': self.id,
                                    'view_mode': 'form',
                                    'target': 'current',
                                    'views': [(False, 'form')],
                                }
                            }
                        }
                    else:
                        raise UserError(_('No site code found in the API response.'))
                else:
                    raise UserError(_('No sites found in the API response.'))
            else:
                raise UserError(_('Failed to fetch site information: %s') % response.text)
        except Exception as e:
            _logger.error('Barid.ma API error: %s', str(e))
            raise UserError(_('Error connecting to Barid.ma API: %s') % str(e))
