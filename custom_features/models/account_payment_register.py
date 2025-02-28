from odoo import _, api, fields, models
import logging

class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'


    def _create_payments(self):
        result = super(AccountPaymentRegister, self)._create_payments()
        all_batches = self._get_batches()
        batches = []
        # Skip batches that are not valid (bank account not trusted but required)
        for batch in all_batches:
            batch_account = self._get_batch_account(batch)
            if self.require_partner_bank_account and not batch_account.allow_out_payment:
                continue
            batches.append(batch)

        for line in batches[0].get('lines', []):  # Assuming 'lines' is part of the batch
            logging.error("Line ID: %s, Move ID: %s", line.id, line.move_id.id)
            logging.error(line.move_id.move_type)
            if line.move_id.move_type == "out_refund":
                sales_orders = line.move_id.line_ids.mapped('sale_line_ids.order_id')
                for order in sales_orders:
                    logging.error("Related Sale Order: %s", order.name)
                    order._action_cancel()
                    logging.info("Sale Order %s has been cancelled.", order.id)

        return result