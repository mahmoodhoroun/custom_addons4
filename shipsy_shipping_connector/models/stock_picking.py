from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import json
import logging
import base64
import io
from PyPDF2 import PdfFileMerger

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = 'stock.picking'
    
    # Shipsy fields
    shipsy_reference_number = fields.Char(string='Chronodiali Reference Number', copy=False, readonly=True)
    shipsy_service_type = fields.Selection([
        ('NORMAL', 'Normal'),
        ('RETURN', 'Return')
    ], string='Chronodiali Service Type', default='NORMAL')
    shipsy_consignment_type = fields.Selection([
        ('forward', 'Forward'),
        ('reverse', 'Reverse')
    ], string='Chronodiali Consignment Type', default='forward')
    shipsy_description = fields.Text(string='Chronodiali Description', 
                                    default="Le client est autorisé à ouvrir le colis.")
    shipsy_connector_id = fields.Many2one('shipping.shipsy.connector', string='Chronodiali Connector', default=lambda self: self._get_default_shipsy_connector())
    shipsy_date = fields.Datetime(string='Chronodiali Submission Date', readonly=True)
    shipsy_label = fields.Binary(string='Chronodiali Label', attachment=True, copy=False)
    shipsy_label_filename = fields.Char(string='Label Filename', copy=False)
    shipsy_is_cancelled = fields.Boolean(string='Is Cancelled in Chronodiali', default=False, copy=False)
    shipsy_pickup_id = fields.Char(string='Chronodiali Pickup ID', copy=False, readonly=True)
    shipsy_is_print = fields.Boolean(string='Is Print', default=False, copy=False)
    
    def _get_default_shipsy_connector(self):
        """Get the first active Shipsy connector"""
        connector = self.env['shipping.shipsy.connector'].search([('active', '=', True)], limit=1)
        return connector.id if connector else False
        
    def action_cancel_shipsy_delivery(self):
        """Cancel delivery in Shipsy"""
        self.ensure_one()
        
        if not self.shipsy_reference_number:
            raise UserError(_('No Shipsy reference number found. Cannot cancel delivery.'))
            
        if self.shipsy_is_cancelled:
            raise UserError(_('This delivery is already cancelled in Shipsy.'))
            
        # Get API key
        if not self.shipsy_connector_id:
            raise UserError(_('No Shipsy connector configured.'))
            
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
        
        try:
            # API endpoint
            url = f"{self.shipsy_connector_id.api_url}/api/customer/integration/consignment/cancel"
            
            # Headers
            headers = {
                'accept': 'application/json',
                'api-key': api_key,
                'content-type': 'application/json'
            }
            
            # Prepare payload
            customer_code = self.shipsy_connector_id.customer_code or ''
            if not customer_code:
                _logger.warning("No customer code configured in Shipsy connector")
                
            payload = json.dumps({
                "AWBNo": [self.shipsy_reference_number],
                "customerCode": customer_code
            })
            
            _logger.info(f"Shipsy Cancel API request: {url}")
            _logger.info(f"Shipsy Cancel API payload: {payload}")
            
            # Send request
            response = requests.post(url, headers=headers, data=payload)
            
            # Process response
            if response.status_code == 200:
                result = response.json()
                _logger.info(f"Shipsy Cancel API response: {result}")
                
                if result.get('status') == 'OK':
                    # Check if there were any failures
                    if result.get('failures') and len(result.get('failures')) > 0:
                        failure = result['failures'][0]
                        # If already cancelled, mark as cancelled in our system too
                        if failure.get('reason') == 'INVALID_CONSIGNMENT_STATUS' and failure.get('current_status') == 'cancelled':
                            self.write({'shipsy_is_cancelled': True})
                            return {
                                'type': 'ir.actions.client',
                                'tag': 'display_notification',
                                'params': {
                                    'title': _('Information'),
                                    'message': _('Delivery is already cancelled in Shipsy.'),
                                    'sticky': False,
                                    'type': 'info',
                                }
                            }
                        else:
                            raise UserError(_('Error cancelling delivery in Shipsy: %s') % failure.get('message', 'Unknown error'))
                    
                    # If no failures and success is true, mark as cancelled
                    if result.get('success'):
                        self.write({'shipsy_is_cancelled': True})
                        self.message_post(body=_(f"Delivery cancelled in Shipsy."))
                        
                        return {
                            'type': 'ir.actions.client',
                            'tag': 'display_notification',
                            'params': {
                                'title': _('Success'),
                                'message': _('Delivery successfully cancelled in Shipsy.'),
                                'sticky': False,
                                'type': 'success',
                            }
                        }
                    else:
                        raise UserError(_('Failed to cancel delivery in Shipsy. No success reported.'))
                else:
                    raise UserError(_('Error in Shipsy API response: %s') % result.get('status', 'Unknown error'))
            else:
                raise UserError(_('Failed to connect to Shipsy API: %s') % response.text)
                
        except Exception as e:
            _logger.error('Shipsy API error: %s', str(e))
            raise UserError(_('Error cancelling delivery in Shipsy: %s') % str(e))
        
    def action_get_shipsy_label(self):
        """Generate and download shipping label from Shipsy API"""
        self.ensure_one()
        
        if not self.shipsy_reference_number:
            raise UserError(_('No Shipsy reference number found. Please send this delivery to Shipsy first.'))
            
        # Get API key
        if not self.shipsy_connector_id:
            raise UserError(_('No Shipsy connector configured.'))
            
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
        
        try:
            # API endpoint
            url = f"{self.shipsy_connector_id.api_url}/api/customer/integration/consignment/shippinglabel/stream?reference_number={self.shipsy_reference_number}&is_small=true"
            
            # Headers
            headers = {
                'accept': 'application/pdf',
                'api-key': api_key,
                'content-type': 'application/json'
            }
            
            _logger.info(f"Shipsy Label API request: {url}")
            
            # Send request
            response = requests.get(url, headers=headers)
            
            # Process response
            if response.status_code == 200:
                # Convert PDF content to base64
                pdf_content = base64.b64encode(response.content)
                
                # Save the PDF as an attachment
                filename = f"shipsy_label_{self.shipsy_reference_number}.pdf"
                self.write({
                    'shipsy_label': pdf_content,
                    'shipsy_label_filename': filename,
                    'shipsy_is_print': True,
                    'print': True
                })
                
                # Return action to download the PDF if not in skip_download context
                if not self.env.context.get('skip_download'):
                    return {
                        'type': 'ir.actions.act_url',
                        'url': f'/web/content/?model=stock.picking&id={self.id}&field=shipsy_label&filename_field=shipsy_label_filename&download=true',
                        'target': 'self',
                    }
                # Otherwise just return success
                return True
            else:
                raise UserError(_('Failed to get label from Shipsy API: %s') % response.text)
                
        except Exception as e:
            _logger.error('Shipsy API error: %s', str(e))
            raise UserError(_('Error getting label from Shipsy API: %s') % str(e))
    
    def action_print_multiple_shipsy_labels(self):
        """Print multiple Shipsy shipping labels in one PDF"""
        # Filter pickings that have Shipsy reference numbers
        pickings_with_refs = self.filtered(lambda p: p.shipsy_reference_number)
        
        if not pickings_with_refs:
            raise UserError(_('No deliveries with Shipsy reference numbers selected.'))
            
        # Get labels for all selected pickings
        merger = PdfFileMerger()
        success_count = 0
        error_count = 0
        error_messages = []
        
        # First, ensure all pickings have labels
        for picking in pickings_with_refs:
            if not picking.shipsy_label:
                try:
                    # Get the label without downloading
                    picking.with_context(skip_download=True).action_get_shipsy_label()
                    if picking.shipsy_label:
                        success_count += 1
                    else:
                        error_count += 1
                        error_messages.append(f"Could not get label for {picking.name}")
                except Exception as e:
                    error_count += 1
                    error_messages.append(f"{picking.name}: {str(e)}")
        
        # Now merge all available PDFs
        merged_pickings = pickings_with_refs.filtered(lambda p: p.shipsy_label)
        if not merged_pickings:
            raise UserError(_('Could not retrieve any shipping labels.'))
            
        for picking in merged_pickings:
            pdf_data = base64.b64decode(picking.shipsy_label)
            pdf_stream = io.BytesIO(pdf_data)
            merger.append(pdf_stream)
            
        # Create the merged PDF
        result_stream = io.BytesIO()
        merger.write(result_stream)
        merger.close()
        
        # Encode the merged PDF
        merged_pdf = base64.b64encode(result_stream.getvalue())
        
        # Create attachment
        attachment = self.env['ir.attachment'].create({
            'name': f'Shipsy_Labels_{len(merged_pickings)}_deliveries.pdf',
            'type': 'binary',
            'datas': merged_pdf,
            'res_model': 'stock.picking',
            'res_id': self[0].id,
            'mimetype': 'application/pdf'
        })
        
        # Return action to download the PDF
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
        
    def action_send_multiple_to_shipsy(self):
        """Send multiple deliveries to Shipsy API in one click"""
        success_count = 0
        error_count = 0
        error_messages = []
        
        for picking in self:
            try:
                # Skip if already has a reference number
                if picking.shipsy_reference_number:
                    continue
                    
                # Skip if no connector selected
                if not picking.shipsy_connector_id:
                    error_count += 1
                    error_messages.append(f"No Shipsy connector for {picking.name}")
                    continue
                
                # Call the single send method without raising exceptions
                result = picking.with_context(skip_notification=True).action_send_to_shipsy()
                if result and result.get('params', {}).get('type') == 'success':
                    success_count += 1
                else:
                    error_count += 1
                    
            except Exception as e:
                error_count += 1
                error_messages.append(f"{picking.name}: {str(e)}")
        
        # Show summary notification
        message = f"Successfully sent {success_count} deliveries to Shipsy."
        if error_count:
            message += f"\nFailed to send {error_count} deliveries."
            if error_messages:
                message += f"\nErrors: {', '.join(error_messages[:5])}"
                if len(error_messages) > 5:
                    message += f" and {len(error_messages) - 5} more."
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Shipsy Delivery Creation'),
                'message': message,
                'sticky': True,
                'type': 'info',
            }
        }
    
    def action_send_to_shipsy(self):
        """Send delivery information to Shipsy API"""
        self.ensure_one()
        
        if not self.shipsy_connector_id:
            raise UserError(_("Please select a Shipsy connector first."))
            
        if self.shipsy_reference_number:
            raise UserError(_("This delivery has already been sent to Shipsy with reference: %s") % self.shipsy_reference_number)
            
        # Calculate total weight
        total_weight = sum(move_line.product_id.weight * move_line.quantity for move_line in self.move_line_ids)
        
        # Determine COD amount
        cod_amount = ""
        if self.shipsy_consignment_type == 'forward' and self.sale_id and self.sale_id.amount_total:
            cod_amount = str(self.sale_id.amount_total)
            
        # Get company details for origin
        company = self.company_id
        
        # Prepare payload
        payload = {
            "load_type": "NON-DOCUMENT",
            "customer_code": "",
            "reference_number": "",
            "service_type_id": self.shipsy_service_type,
            "consignment_type": self.shipsy_consignment_type,
            "cod_collection_mode": "cash",
            "cod_amount": cod_amount,
            "hub_code": "",
            "origin_details": {
                "name": company.name,
                "phone": company.phone or "",
                "address_line_1": company.street or "",
                "pincode": company.zip or "",
                "city": company.city or "",
                "country": company.country_id.name if company.country_id else "",
                "latitude": "",
                "longitude": ""
            },
            "destination_details": {
                "name": self.partner_id.name,
                "phone": self.partner_id.phone or "",
                "address_line_1": self.partner_id.street or "",
                "pincode": self.partner_id.zip or "",
                "city": self.partner_id.city or "",
                "country": self.partner_id.country_id.name if self.partner_id.country_id else "",
                "latitude": "",
                "longitude": ""
            },
            "pieces_detail": [
                {
                    "description": self.shipsy_description,
                    "declared_value": "",
                    "weight": str(total_weight) if total_weight else "",
                    "height": "",
                    "length": "",
                    "width": "",
                    "weight_unit": "kg",
                    "quantity": "1"
                }
            ]
        }
        
        try:
            # API endpoint
            url = f"{self.shipsy_connector_id.api_url}/api/customer/integration/consignment/upload/softdata/v2"
            
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
                # Continue with the original API key if parsing fails
                
            # Headers
            headers = {
                'accept': 'application/json',
                'api-key': api_key,
                'content-type': 'application/json'
            }
            _logger.info(f"Shipsy API request: {url}")
            _logger.info(f"Shipsy API headers: {headers}")
            _logger.info(f"Shipsy API key used: {api_key}")
            
            # Send request
            response = requests.post(url, headers=headers, data=json.dumps(payload))
            
            # Process response
            if response.status_code in [200, 201]:
                result = response.json()
                _logger.info(f"Shipsy API response: {result}")
                
                if result.get('success') and result.get('reference_number'):
                    self.write({
                        'shipsy_reference_number': result.get('reference_number'),
                        'shipsy_date': fields.Datetime.now(),
                    })
                    
                    # Only show notification if not in skip_notification context
                    if not self.env.context.get('skip_notification'):
                        return {
                            'type': 'ir.actions.client',
                            'tag': 'display_notification',
                            'params': {
                                'title': _('Success'),
                                'message': _('Delivery successfully sent to Shipsy with reference: %s') % result.get('reference_number'),
                                'sticky': False,
                                'type': 'success',
                                'next': {
                                    'type': 'ir.actions.act_window',
                                    'res_model': 'stock.picking',
                                    'res_id': self.id,
                                    'view_mode': 'form',
                                    'target': 'current',
                                    'views': [(False, 'form')],
                                }
                            }
                        }
                    else:
                        # Return a simple success result for batch processing
                        return {
                            'params': {
                                'type': 'success',
                                'reference_number': result.get('reference_number')
                            }
                        }
                else:
                    raise UserError(_('Error in Shipsy API response: %s') % response.text)
            else:
                raise UserError(_('Failed to connect to Shipsy API: %s') % response.text)
                
        except Exception as e:
            _logger.error('Shipsy API error: %s', str(e))
            raise UserError(_('Error connecting to Shipsy API: %s') % str(e))
