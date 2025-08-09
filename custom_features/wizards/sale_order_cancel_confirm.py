from odoo import models, fields, api, _

class SaleOrderCancelConfirm(models.TransientModel):
    _name = 'sale.order.cancel.confirm'
    _description = 'Sale Order Cancellation Confirmation'

    order_id = fields.Many2one('sale.order', string='Sale Order', required=True)
    reason = fields.Selection([
        ('wrong_number', 'Mauvais numéro'),
        ('call_rejected', 'Appel rejeté'),
        ('duplicated_order', 'Commande en double'),
        ('out_of_coverage', 'Hors couverture'),
        ('out_of_stock', 'Rupture de stock'),
        ('no_reply', 'Pas de réponse'),
        ('fake_order', 'Commande frauduleuse'),
        ('modification_de_commande', 'Modification de commande'),
        ('annulee_sans_reponse', 'Annulée sans réponse'),
    ], string='Motif d\'annulation', required=True)
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
        for pack in self.order_id.picking_ids:
            if pack.shipsy_reference_number and pack.shipsy_is_cancelled == False:
                pack.action_cancel_shipsy_delivery()
            
        # Call the super method to perform the actual cancellation
        return self.order_id.with_context(bypass_cancel_wizard=True).action_cancel()
