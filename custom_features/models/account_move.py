from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class AccountMove(models.Model):
    _inherit = 'account.move'

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