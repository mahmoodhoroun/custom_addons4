from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import base64
import io
import json
import zipfile
import requests
from werkzeug import urls
from datetime import timedelta

class AccountMove(models.Model):
    _inherit = 'account.move'
    
    def _upload_to_google_drive(self, file_data, filename, backup_config=None):
        """Upload a file to Google Drive using the configured settings from auto_database_backup"""
        # If backup_config is not provided, find the first active Google Drive backup configuration
        if not backup_config:
            backup_config = self.env['db.backup.configure'].search([
                ('backup_destination', '=', 'google_drive'),
                ('gdrive_refresh_token', '!=', False),
                ('google_drive_folder_key', '!=', False)
            ], limit=1)
        
        if not backup_config:
            # Return error message instead of raising exception
            return {'error': 'No Google Drive configuration found'}
            
        # Check if Google Drive folder key is configured
        if not backup_config.google_drive_folder_key:
            return {'error': 'Google Drive folder ID not configured'}
            
        # Check if token is expired and refresh if needed
        try:
            if not backup_config.gdrive_access_token or \
               (backup_config.gdrive_token_validity and backup_config.gdrive_token_validity <= fields.Datetime.now()):
                backup_config.generate_gdrive_refresh_token()
        except Exception as e:
            return {'error': f'Failed to refresh Google Drive token: {str(e)}'}
            
        # Upload file to Google Drive
        headers = {
            "Authorization": f"Bearer {backup_config.gdrive_access_token}"
        }
        
        # Prepare the metadata for the file
        para = {
            "name": filename,
            "parents": [backup_config.google_drive_folder_key],
        }
        
        # Create multipart request
        files = {
            'data': ('metadata', json.dumps(para), 'application/json; charset=UTF-8'),
            'file': (filename, file_data, 'application/zip')
        }
        
        try:
            # Upload to Google Drive
            response = requests.post(
                "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart",
                headers=headers,
                files=files,
                timeout=30  # Add timeout to prevent hanging
            )
            
            if response.status_code not in (200, 201):
                return {'error': f'Upload failed with status {response.status_code}: {response.text}'}
                
            return response.json()
        except requests.RequestException as e:
            return {'error': f'Request error: {str(e)}'}
        except Exception as e:
            return {'error': f'Unexpected error: {str(e)}'}

    def action_print_invoices_zip(self):
        """Print selected invoices and combine them into a ZIP file for download and upload to Google Drive"""
        if not self:
            raise ValidationError(_('Please select at least one invoice to print.'))
            
        # Create a ZIP file in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            for invoice in self:
                # Generate PDF report for each invoice
                pdf_content, _ = self.env['ir.actions.report']._render_qweb_pdf(
                    'account.account_invoices', invoice.ids
                )
                
                # Add the PDF to the ZIP file with a meaningful filename
                filename = f"Invoice_{invoice.name.replace('/', '_')}.pdf"
                zip_file.writestr(filename, pdf_content)
        
        # Get the ZIP file data
        zip_buffer.seek(0)
        zip_data_binary = zip_buffer.read()
        zip_data = base64.b64encode(zip_data_binary)
        
        # Store a copy of the raw data for Google Drive upload
        raw_zip_data = zip_data_binary
        
        # Create attachment for download
        attachment = self.env['ir.attachment'].create({
            'name': 'Invoices.zip',
            'type': 'binary',
            'datas': zip_data,
            'mimetype': 'application/zip',
        })
        
        # Check if auto_database_backup module is installed
        if self.env['ir.module.module'].sudo().search([('name', '=', 'auto_database_backup'), ('state', '=', 'installed')]):
            # Try to upload to Google Drive
            try:
                # Find Google Drive configurations with tokens
                backup_config = self.env['db.backup.configure'].search([
                    ('backup_destination', '=', 'google_drive'),
                    ('gdrive_refresh_token', '!=', False),  # Check for refresh token instead of computed field
                    ('google_drive_folder_key', '!=', False)
                ], limit=1)
                
                if not backup_config:
                    raise ValidationError("No valid Google Drive configuration found")
                    
                # Create a filename with timestamp
                timestamp = fields.Datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                filename = f"Invoices_{timestamp}.zip"
                
                # Upload to Google Drive - use the raw binary data, not base64 encoded
                drive_response = self._upload_to_google_drive(raw_zip_data, filename, backup_config)
                
                # Check if there was an error
                if drive_response and 'error' in drive_response:
                    message = f"Failed to upload to Google Drive: {drive_response['error']}"
                    self.env['bus.bus']._sendone(
                        self.env.user.partner_id, 
                        'notification', 
                        {
                            'type': 'warning',
                            'title': "Google Drive Upload",
                            'message': message,
                            'sticky': True,
                        }
                    )
                else:
                    # Show success message
                    message = "Invoices successfully uploaded to Google Drive"
                    self.env['bus.bus']._sendone(
                        self.env.user.partner_id, 
                        'notification', 
                        {
                            'type': 'success',
                            'title': "Google Drive Upload",
                            'message': message,
                            'sticky': False,
                        }
                    )
            except Exception as e:
                # Log the error but don't stop the download process
                message = f"Failed to upload to Google Drive: {str(e)}"
                self.env['bus.bus']._sendone(
                    self.env.user.partner_id, 
                    'notification', 
                    {
                        'type': 'warning',
                        'title': "Google Drive Upload",
                        'message': message,
                        'sticky': True,
                    }
                )
        
        
        # Return action to download the attachment
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
    
    def action_bulk_confirm_invoices(self):
        use_wizard = self.env.context.get('default_use_wizard')

        if not use_wizard:
            raise ValidationError(_('Wizard context not set.'))

        draft_invoices = self.filtered(lambda inv: inv.state == 'draft')
        if not draft_invoices:
            raise ValidationError(_('Please select at least one draft invoice.'))
            
        # Get default values from the first invoice
        first_invoice = draft_invoices[0]
        wizard = self.env['bulk.confirm.invoice.wizard'].create({
            'invoice_date': first_invoice.invoice_date,
            'payment_term_id': first_invoice.invoice_payment_term_id.id
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'bulk.confirm.invoice.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new'
        }