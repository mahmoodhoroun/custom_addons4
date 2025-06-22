from odoo import models, fields, api, _

class SaleOrderCancelConfirm(models.TransientModel):
    _name = 'sale.order.cancel.confirm'
    _description = 'Sale Order Cancellation Confirmation'

    order_id = fields.Many2one('sale.order', string='Sale Order', required=True)
    reason = fields.Selection([
        ('wrong_number', 'Wrong number'),
        ('call_rejected', 'Call rejected'),
        ('duplicated_order', 'Duplicated order'),
        ('out_of_coverage', 'Out of coverage'),
        ('out_of_stock', 'Out of stock'),
        ('no_reply', 'No reply'),
    ], string='Cancellation Reason', required=True)
    confirmation_message = fields.Text(string='Confirmation Message', readonly=True)
    
    @api.onchange('reason')
    def _onchange_reason(self):
        if self.reason:
            self.confirmation_message = _('Are you sure you want to cancel this order due to: %s?') % dict(self._fields['reason'].selection).get(self.reason)

    def action_confirm_cancel(self):
        """Confirm the cancellation of the sale order"""
        self.ensure_one()
        # Update the order's reason before cancelling
        self.order_id.cancel_reason = self.reason
        # Call the super method to perform the actual cancellation
        return self.order_id.with_context(bypass_cancel_wizard=True).action_cancel()
