from odoo import api, fields, models


class BulkConfirmInvoiceLine(models.TransientModel):
    _name = 'bulk.confirm.invoice.line'
    _description = 'Per-Invoice Confirm Data'

    wizard_id = fields.Many2one('bulk.confirm.invoice.wizard', required=True)
    invoice_id = fields.Many2one('account.move', required=True, domain="[('move_type','=','out_invoice')]")
    invoice_date = fields.Date(string="Invoice Date")
    payment_term_id = fields.Many2one('account.payment.term', string="Payment Term")



class BulkConfirmWizard(models.TransientModel):
    _name = 'bulk.confirm.invoice.wizard'
    _description = 'Bulk Confirm Invoices'

    invoice_line_ids = fields.One2many('bulk.confirm.invoice.line', 'wizard_id', string="Invoices")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        invoice_ids = self.env.context.get('default_invoice_ids', [])
        lines = []
        for inv in self.env['account.move'].browse(invoice_ids):
            if inv.state != 'draft':
                continue
            lines.append((0, 0, {
                'invoice_id': inv.id,
                'invoice_date': inv.invoice_date,
                'payment_term_id': inv.invoice_payment_term_id.id,
            }))
        res['invoice_line_ids'] = lines
        return res

    def confirm_all(self):
        for line in self.invoice_line_ids:
            invoice = line.invoice_id
            invoice.write({
                'invoice_date': line.invoice_date,
                'invoice_payment_term_id': line.payment_term_id.id,
            })
            if invoice.state == 'draft':
                invoice.action_post()