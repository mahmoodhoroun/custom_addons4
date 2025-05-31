import requests
import json
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    crbt_type = fields.Selection([
        ('None', 'None'),
        ('Cash', 'Cash'),
        ('Check', 'Check')
    ], string='CrbtType', default='Cash')
    
    barid_ma_tracking = fields.Char(string='Barid.ma Tracking Number', readonly=True, copy=False)
    barid_ma_package_id = fields.Char(string='Barid.ma Package ID', readonly=True, copy=False)
    barid_ma_contract_id = fields.Char(string='Barid.ma Contract ID', readonly=True, copy=False)
    barid_ma_fim_generated = fields.Boolean(string='FIM Generated', default=False, readonly=True, copy=False)
    barid_ma_id_fim = fields.Char(string='Barid.ma ID FIM', readonly=True, copy=False)
    
    def _get_barid_ma_destination_id(self, connector, city):
        """Get destination ID from Barid.ma API based on city name"""
        if not city:
            raise UserError(_('City name is required for delivery. Please set a city in the delivery address.'))
        
        # Prepare API URL
        url = f"{connector.api_url}/Locality/search"
        
        # Prepare the payload
        payload = {
            "value": city,
            "take": 10
        }
        
        # Prepare headers with token
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {connector.token}'
        }
        
        try:
            # Make the API request
            response = requests.post(url, headers=headers, data=json.dumps(payload))
            
            # Process the response
            if response.status_code == 200:
                localities = response.json()
                _logger.info(f"Barid.ma localities response: {localities}")
                
                if isinstance(localities, list) and localities:
                    # Try to find exact match first
                    for locality in localities:
                        if locality.get('nameLocality', '').upper() == city.upper():
                            return locality.get('idLocality')
                    
                    # If no exact match but we have results, use the first one
                    if localities[0].get('idLocality'):
                        return localities[0].get('idLocality')
                
                # If we get here, no matching city was found
                raise UserError(_('City "%s" not found in Barid.ma system. Please check the city name or contact support.') % city)
            else:
                raise UserError(_('Failed to get localities from Barid.ma API: %s') % response.text)
        except Exception as e:
            _logger.error(f"Error getting locality ID: {str(e)}")
            raise UserError(_('Error connecting to Barid.ma API to verify city: %s') % str(e))
    
    def _format_moroccan_phone(self, number):
        if not number:
            return ""
        # Remove spaces, dashes, and parentheses
        cleaned = number.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        
        # Normalize +212 or 212 to 0
        if cleaned.startswith("+212"):
            cleaned = "0" + cleaned[4:]
        elif cleaned.startswith("212"):
            cleaned = "0" + cleaned[3:]

        return cleaned
    
    def action_create_barid_ma_package(self, record):
        """Create package in Barid.ma API"""
        record.ensure_one()
        
        # Get the Barid.ma connector configuration
        connector = record.env['shipping.barid.ma.connector'].search([('active', '=', True)], limit=1)
        if not connector:
            raise UserError(_('No active Barid.ma connector found. Please configure one first.'))
        
        # Ensure we have a valid token
        if not connector.token:
            connector.get_auth_token()
        
        # Get IdDestination based on partner city
        partner = record.partner_id
        if not partner:
            raise UserError(_('No delivery address found.'))
        id_destination = record._get_barid_ma_destination_id(connector, partner.city)
        _logger.info(f"IdDestination: {id_destination}")
        _logger.info("****************************************")
    
        # Prepare API URL
        url = f"{connector.api_url}/Package/bulkInsert/genereFim/false"
        
        # Get sale order
        sale_order = record.env['sale.order'].search([('name', '=', record.origin)], limit=1) if record.origin else False
            
        # Calculate total weight
        total_weight = sum(move_line.product_id.weight * move_line.quantity for move_line in record.move_line_ids)
        if total_weight <= 0:
            total_weight = 1.0  # Default weight if no weight found
        
        # Get company phone
        company_phone = record.company_id.phone or ''
        
        # Prepare customer name
        first_name = partner.name
        last_name = ""
        if ' ' in partner.name:
            name_parts = partner.name.split(' ', 1)
            first_name = name_parts[0]
            last_name = name_parts[1]
        
        # Determine which contract ID to use based on city ID
        special_city_ids = [2051, 8, 2, 1, 1688, 1416, 1857, 1734, 2559, 1718, 2692, 22, 2705, 1360, 2714, 2391, 2330, 2399, 1397, 1680, 1409, 30]
        contract_id = connector.id_contract1 if id_destination in special_city_ids else connector.id_contract2
        _logger.info(f"Contract ID: {contract_id}")
        _logger.info("****************************************")
        # Store the contract ID for later use in FIM generation
        record.barid_ma_contract_id = contract_id
        
        # Prepare the payload
        payload = [{
            "IdContract": contract_id or 0,
            "IdDeposit": connector.id_deposit or "",
            "IdDestination": id_destination,
            "DeliveryMode": "AtAddress",
            "NeighborhoodAddress": partner.contact_address or partner.street or "",
            "StreetAddress": partner.city or "",
            "IdRelayPoint": None,
            "IdSite": None,
            "Cab": "",
            "RefOrder": record.origin or "New",
            "NameRs": last_name,
            "FirstName": first_name,
            "PhoneRecipient": record._format_moroccan_phone(partner.phone or partner.mobile),
            "PhoneSender": company_phone,
            "VD": None,
            "Weight": total_weight,
            "CrbtType": record.crbt_type,
            "CrbtValue": sale_order.amount_total if sale_order and record.crbt_type == 'Cash' else 0,
            "Fragile": False,
            "POD": False,
            "BL": False,
            "IdProvider": None,
            "Length": 0,
            "Width": 0,
            "Height": 0,
            "ProductCode": "AMA"
        }]
        
        # Prepare headers with token
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {connector.token}'
        }
        
        try:
            # Make the API request
            response = requests.post(url, headers=headers, data=json.dumps(payload))
            
            # Process the response
            if response.status_code == 200:
                result = response.json()
                _logger.info(f"Barid.ma API response: {result}")
                
                if isinstance(result, dict) and result.get('success') and len(result.get('success')) > 0:
                    # Extract tracking number and package ID from the response
                    package_info = result.get('success')[0]
                    if package_info.get('cab'):
                        record.barid_ma_tracking = package_info.get('cab')
                    if package_info.get('idPackage'):
                        record.barid_ma_package_id = str(package_info.get('idPackage'))
                    
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Success'),
                            'message': _('Package created successfully in Barid.ma. Tracking number: %s') % record.barid_ma_tracking,
                            'sticky': False,
                            'type': 'success',
                            'next': {
                                'type': 'ir.actions.act_window',
                                'res_model': 'stock.picking',
                                'res_id': record.id,
                                'view_mode': 'form',
                                'target': 'current',
                                'views': [(False, 'form')],
                            }
                        }
                    }
                else:
                    raise UserError(_('Invalid response from Barid.ma API: %s') % response.text)
            else:
                # Handle error response
                error_message = response.text
                try:
                    error_data = response.json()
                    if isinstance(error_data, dict) and error_data.get('message'):
                        error_message = error_data.get('message')
                except:
                    pass
                
                raise UserError(_('Failed to create package in Barid.ma API: %s') % error_message)
                
        except Exception as e:
            _logger.error('Barid.ma API error: %s', str(e))
            raise UserError(_('Error connecting to Barid.ma API: %s') % str(e))
    
    def create_single_package(self):
        self.ensure_one()
        try:
            self.action_create_barid_ma_package(self)
        except Exception as e:
            raise UserError(_("Error creating package in Barid.ma API: %s") % str(e))
    
    def create_multiple_packages(self):
        packages_array = self

        for record in packages_array:
            try:
                record.action_create_barid_ma_package(record)
            
            except Exception as e:
                pass
            
    def action_delete_barid_ma_package(self):
        """Delete package from Barid.ma API"""
        self.ensure_one()
        
        if not self.barid_ma_package_id:
            raise UserError(_('No Barid.ma package ID found. Cannot delete package.'))
            
        # Get the Barid.ma connector configuration
        connector = self.env['shipping.barid.ma.connector'].search([('active', '=', True)], limit=1)
        if not connector:
            raise UserError(_('No active Barid.ma connector found. Please configure one first.'))
        
        # Ensure we have a valid token
        if not connector.token:
            connector.get_auth_token()
        
        # Prepare API URL
        url = f"{connector.api_url}/Package/{self.barid_ma_package_id}"
        
        # Prepare headers with token
        headers = {
            'Authorization': f'Bearer {connector.token}'
        }
        
        try:
            # Make the API request
            response = requests.request("DELETE", url, headers=headers, data={})
            _logger.info(f"Barid.ma package deletion response: {response.status_code}")
            _logger.info(f"Barid.ma package deletion response text: {response.text}")
            
            # Process the response
            if response.status_code == 200:
                # Clear the package data
                self.barid_ma_package_id = False
                self.barid_ma_tracking = False
                self.barid_ma_fim_generated = False
                self.barid_ma_contract_id = False
                self.barid_ma_id_fim = False
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Package Deleted'),
                        'message': _('Successfully deleted package from Barid.ma'),
                        'sticky': False,
                        'type': 'success',
                        'next': {'type': 'ir.actions.client', 'tag': 'reload'}
                    }
                }
            else:
                # Handle error response
                error_message = response.text
                try:
                    error_data = response.json()
                    error_message = error_data.get('message', error_message)
                except:
                    pass
                
                raise UserError(_('Failed to delete package: %s') % error_message)
                
        except Exception as e:
            _logger.error('Barid.ma API error: %s', str(e))
            raise UserError(_('Error connecting to Barid.ma API: %s') % str(e))
    
    def delete_multiple_packages(self):
        """Delete multiple packages from Barid.ma API"""
        success_count = 0
        error_messages = []
        
        for record in self:
            if not record.barid_ma_package_id:
                error_messages.append(_('No package ID found for %s') % record.name)
                continue
                
            try:
                record.action_delete_barid_ma_package()
                success_count += 1
            except Exception as e:
                error_messages.append(f"{record.name}: {str(e)}")
        
        # Return appropriate message
        if success_count > 0:
            message = _('Successfully deleted %d packages.') % success_count
            if error_messages:
                message += _('\nErrors occurred for some packages: %s') % '\n'.join(error_messages)
                
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Package Deletion Result'),
                    'message': message,
                    'sticky': bool(error_messages),  # Make sticky if there were errors
                    'type': 'success' if not error_messages else 'warning',
                    'next': {'type': 'ir.actions.client', 'tag': 'reload'}
                }
            }
        else:
            raise UserError(_('Failed to delete any packages:\n%s') % '\n'.join(error_messages))
            
    def action_print_barid_ma_label(self):
        """Print the Barid.ma shipping label"""
        self.ensure_one()
        
        if not self.barid_ma_tracking:
            raise UserError(_('No Barid.ma tracking number found. Please create a package first.'))
            
        return self.env.ref('shipping_api_connector.action_report_barid_ma_label').report_action(self)
        
    def action_generate_fim(self):
        """Generate FIM for Barid.ma packages"""
        # Filter records that can have FIMs generated
        valid_pickings = self.filtered(lambda p: p.barid_ma_tracking and not p.barid_ma_fim_generated)
        
        if not valid_pickings:
            raise UserError(_('No valid deliveries found for FIM generation. Ensure they have tracking numbers and have not already had FIMs generated.'))
            
        # Get the Barid.ma connector configuration
        connector = self.env['shipping.barid.ma.connector'].search([('active', '=', True)], limit=1)
        if not connector:
            raise UserError(_('No active Barid.ma connector found. Please configure one first.'))
            
        # Ensure we have a valid token
        if not connector.token:
            connector.get_auth_token()
            
        # Ensure we have a site ID
        if not connector.id_site:
            raise UserError(_('No site ID found in the connector. Please use the "Get IdSite" button in the connector configuration.'))
        
        # Collect all tracking numbers
        tracking_numbers = []
        for rec in self:
            if not rec.barid_ma_tracking:
                raise UserError(_('No tracking number found for delivery %s. Please create a package first.') % rec.name)
            tracking_numbers.append(rec.barid_ma_tracking)
        
        contract_ids = []
        for rec in self:
            contract_ids.append(rec.barid_ma_contract_id)
        _logger.info(f"Contract IDs: {contract_ids}")
        _logger.info(f"************************************************")
        contract_id = 0
        if contract_ids and all(x == contract_ids[0] for x in contract_ids):
            contract_id = contract_ids[0]
            _logger.info(f"Contract ID: {contract_id}")
            _logger.info(f"************************************************")
            # Prepare API URL
            url = f"{connector.api_url}/Package/write-order-csv/contract/{contract_id}/site/{connector.id_site}"
            
            # Prepare the payload with tracking numbers
            payload = json.dumps(tracking_numbers)
            
            # Prepare headers with token
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {connector.token}'
            }
            
            try:
                # Make the API request
                response = requests.post(url, headers=headers, data=payload)
                _logger.info(f"Barid.ma FIM generation response: {response.status_code}")
                _logger.info("****************************************")
                # Process the response
                if response.status_code == 204:
                    # Status 204 means success but no content to return
                    _logger.info("Barid.ma FIM generation successful with status 204 (No Content)")
                    
                    # Mark the FIMs as generated
                    for rec in valid_pickings:
                        rec.barid_ma_fim_generated = True
                    
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('FIM Generation Successful'),
                            'message': _('Successfully generated FIMs for %d packages') % len(valid_pickings),
                            'sticky': False,
                            'type': 'success',
                            'next': {'type': 'ir.actions.client', 'tag': 'reload'}
                        }
                    }
                else:
                    # Handle error response
                    error_message = response.text
                    try:
                        error_data = response.json()
                        # if isinstance(error_data, dict) and error_data.get('message'):
                        error_message = error_data.get('message')
                    except:
                        pass
                    
                    raise UserError(_('Failed to generate FIMs: %s') % error_message)
                    
            except Exception as e:
                _logger.error('Barid.ma API error: %s', str(e))
                raise UserError(_('Error connecting to Barid.ma API: %s') % str(e))
        
        else:
            raise UserError(_('All packages must use the same contract ID for FIM generation.'))
            