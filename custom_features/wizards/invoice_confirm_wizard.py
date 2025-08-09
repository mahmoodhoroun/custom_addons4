from odoo import api, fields, models


class BulkConfirmWizard(models.TransientModel):
    _name = 'bulk.confirm.invoice.wizard'
    _description = 'Bulk Confirm Invoices'

    invoice_date = fields.Date(string="Invoice Date")
    payment_term_id = fields.Many2one('account.payment.term', string="Payment Term")
    payment_reference = fields.Char(string="Payment Reference")
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # Get the first invoice's date and payment term as default values
        invoice_ids = self.env.context.get('default_invoice_ids', [])
        if invoice_ids:
            invoice = self.env['account.move'].browse(invoice_ids[0])
            res['invoice_date'] = invoice.invoice_date
            res['payment_term_id'] = invoice.invoice_payment_term_id.id
        return res

    def confirm_all(self):
        invoice_ids = self.env.context.get('active_ids', [])
        invoices = self.env['account.move'].browse(invoice_ids)
        
        # Update all selected invoices with the same date and payment term
        for invoice in invoices:
            if invoice.state != 'draft':
                continue
                
            invoice.write({
                'invoice_date': self.invoice_date,
                'invoice_payment_term_id': self.payment_term_id.id,
                'payment_reference': self.payment_reference
            })
            invoice.action_post()