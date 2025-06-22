from odoo import models, fields, api, _
from odoo.exceptions import UserError

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    receive_products = fields.Many2one('stock.location', string='Receive Products')
    receipt_ids = fields.One2many('stock.picking', 'sale_id', string="Receipts")
    receipt_count = fields.Integer(
        string='Receipts Count', compute='_compute_receipt_count', store=True
    )
    customr_phone = fields.Char(string='Customer Phone', compute='_compute_customer_phone')
    cancel_reason = fields.Selection([
        ('wrong_number', 'Wrong number'),
        ('call_rejected', 'Call rejected'),
        ('duplicated_order', 'Duplicated order'),
        ('out_of_coverage', 'Out of coverage'),
        ('out_of_stock', 'Out of stock'),
        ('no_reply', 'No reply'),
    ], string='Cancellation Reason', tracking=True)

    status2 = fields.Selection([
        ('line_busy', 'Line busy'),
        ('disconnected', 'Disconnected'),
        ('no_reply', 'No reply'),
        ('callback_requested', 'Callback requested'),
    ], string='Status2', tracking=True)

    def action_cancel_custom(self):
        """Override the standard cancel method to show the wizard"""
        # If we're bypassing the wizard (coming from the wizard itself), call the super method
        if self.env.context.get('bypass_cancel_wizard'):
            return super(SaleOrder, self).action_cancel()
            
        # Otherwise, show the wizard
        return {
            'type': 'ir.actions.act_window',
            'name': _('Select Cancellation Reason'),
            'res_model': 'sale.order.cancel.confirm',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_order_id': self.id,
                'default_reason': self.cancel_reason or False,
            }
        }
        
    def _action_cancel(self):
        """Actual cancellation method called from the wizard"""
        return super(SaleOrder, self)._action_cancel()

    def _compute_customer_phone(self):
        for order in self:
            order.customr_phone = order.partner_id.phone or order.partner_id.mobile


    @api.depends('receipt_ids')
    def _compute_receipt_count(self):
        for order in self:
            # Only count receipts with picking type 'incoming'
            incoming_receipts = order.receipt_ids.filtered(lambda p: p.picking_type_id.code == 'incoming')
            order.receipt_count = len(incoming_receipts)

    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()

        additional_products = []
        for line in self.order_line:
            product = line.product_template_id
            bom = self.env['mrp.bom'].search([
                ('product_tmpl_id', '=', product.id),
                ('type', '=', 'phantom')
            ], limit=1)

            if bom:
                for additional_product in bom.additional_product_ids:
                    additional_products.append({
                        'product_id': additional_product.product_id.id,
                        'quantity': additional_product.quantity * line.product_uom_qty,
                        'uom_id': additional_product.product_id.uom_id.id,
                        'name': additional_product.product_id.display_name,
                    })

        if additional_products:
            picking = self._create_single_receipt(additional_products)
            self.write({'receipt_ids': [(4, picking.id)]})  # Link picking to the Sale Order

        return res

    def _create_single_receipt(self, additional_products):
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'incoming'),
            ('warehouse_id.company_id', '=', self.company_id.id)
        ], limit=1)

        if not picking_type:
            raise ValueError("No incoming picking type found for this company.")

        bom = self.env['mrp.bom'].search([
            ('product_tmpl_id', '=', self.order_line[0].product_template_id.id ),
            ('type', '=', 'phantom')
        ], limit=1)

        source_location_id = bom.from_products.id  or self.env.ref('stock.stock_location_stock').id
        destination_location_id = bom.receive_products.id or picking_type.default_location_dest_id.id

        if not source_location_id:
            raise ValueError("The source location (location_id) is not configured for the selected picking type.")
        if not destination_location_id:
            raise ValueError("The destination location (location_dest_id) is not set or configured.")

        move_lines = [
            (0, 0, {
                'product_id': product['product_id'],
                'product_uom_qty': product['quantity'],
                'product_uom': product['uom_id'],
                'name': product['name'],
                'location_id': source_location_id,
                'location_dest_id': destination_location_id,
            })
            for product in additional_products
        ]

        picking_vals = {
            'picking_type_id': picking_type.id,
            'location_id': source_location_id,
            'location_dest_id': destination_location_id,
            'move_ids_without_package': move_lines,
            'origin': self.name,
            'sale_id': self.id,  # Link the picking to the Sale Order
        }

        picking = self.env['stock.picking'].create(picking_vals)

        return picking

    def action_view_receipts(self):
        """
        Action for the smart button to show linked receipts.
        """
        action = self.env.ref('stock.action_picking_tree_all').read()[0]
        action['domain'] = [('id', 'in', self.receipt_ids.ids)]
        action['context'] = dict(self.env.context, create=False)
        return action
