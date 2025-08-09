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

    customer_phone = fields.Char(string='Customer Phone', compute='_compute_customer_phone')
    
    def _compute_customer_phone(self):
        for move in self:
            move.customer_phone = move.partner_id.phone
    
    def _upload_to_google_drive(self, file_data, filename, backup_config=None, mime_type='application/pdf'):
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
            'file': (filename, file_data, mime_type)
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

    def action_print_invoices_pdf(self):
        """Print selected invoices as individual PDF files and upload them to Google Drive"""
        if not self:
            raise ValidationError(_('Please select at least one invoice to print.'))
        
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
                
                uploaded_files = []
                failed_uploads = []
                
                # Upload each invoice PDF individually
                for invoice in self:
                    try:
                        # Generate PDF report for each invoice
                        pdf_content, _ = self.env['ir.actions.report']._render_qweb_pdf(
                            'account.account_invoices', invoice.ids
                        )
                        
                        # Create filename with timestamp
                        timestamp = fields.Datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                        filename = f"Invoice_{invoice.name.replace('/', '_')}_{timestamp}.pdf"
                        
                        # Upload to Google Drive
                        drive_response = self._upload_to_google_drive(pdf_content, filename, backup_config, 'application/pdf')
                        
                        # Check if there was an error
                        if drive_response and 'error' in drive_response:
                            failed_uploads.append(f"{invoice.name}: {drive_response['error']}")
                        else:
                            uploaded_files.append(invoice.name)
                            
                    except Exception as e:
                        failed_uploads.append(f"{invoice.name}: {str(e)}")
                
                # Show summary notification
                if uploaded_files and not failed_uploads:
                    message = f"Successfully uploaded {len(uploaded_files)} invoice(s) to Google Drive"
                    notification_type = 'success'
                    sticky = False
                elif uploaded_files and failed_uploads:
                    message = f"Uploaded {len(uploaded_files)} invoice(s) successfully. Failed: {len(failed_uploads)}"
                    notification_type = 'warning'
                    sticky = True
                else:
                    message = f"Failed to upload all {len(failed_uploads)} invoice(s) to Google Drive"
                    notification_type = 'danger'
                    sticky = True
                
                self.env['bus.bus']._sendone(
                    self.env.user.partner_id, 
                    'notification', 
                    {
                        'type': notification_type,
                        'title': "Google Drive Upload",
                        'message': message,
                        'sticky': sticky,
                    }
                )
                
            except Exception as e:
                # Log the error
                message = f"Failed to upload invoices to Google Drive: {str(e)}"
                self.env['bus.bus']._sendone(
                    self.env.user.partner_id, 
                    'notification', 
                    {
                        'type': 'danger',
                        'title': "Google Drive Upload",
                        'message': message,
                        'sticky': True,
                    }
                )
        else:
            # Show message that auto_database_backup module is not installed
            self.env['bus.bus']._sendone(
                self.env.user.partner_id, 
                'notification', 
                {
                    'type': 'warning',
                    'title': "Google Drive Upload",
                    'message': "auto_database_backup module is not installed. Cannot upload to Google Drive.",
                    'sticky': True,
                }
            )
        
        # Return a simple notification action instead of download
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Invoice Upload',
                'message': 'Invoice upload process completed. Check notifications for details.',
                'type': 'info',
                'sticky': False,
            }
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