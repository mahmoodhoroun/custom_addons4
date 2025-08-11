from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    receive_products = fields.Many2one('stock.location', string='Receive Products')
    receipt_ids = fields.One2many('stock.picking', 'sale_id', string="Receipts")
    receipt_count = fields.Integer(
        string='Receipts Count', compute='_compute_receipt_count', store=True
    )
    customr_phone = fields.Char(string='Téléphone', compute='_compute_customer_phone', readonly=False)
    cancel_reason = fields.Selection([
        ('wrong_number', 'Mauvais numéro'),
        ('call_rejected', 'Appel rejeté'),
        ('duplicated_order', 'Commande en double'),
        ('out_of_coverage', 'Hors couverture'),
        ('out_of_stock', 'Rupture de stock'),
        ('no_reply', 'Pas de réponse'),
        ('fake_order', 'Commande frauduleuse'),
        ('modification_de_commande', 'Modification de commande'),
        ('annulee_sans_reponse', 'Annulée sans réponse'),
    ], string='Motif d\'annulation', tracking=True)

    status2 = fields.Selection([
        ('line_busy', 'Ligne occupée'),
        ('disconnected', 'Appel coupé'),
        ('no_reply', 'Pas de réponse'),
        ('callback_requested', 'Rappel demandé'),
    ], string='Résultat de l\'appel', tracking=True)
    
    delivery_ids = fields.One2many('stock.picking', 'sale_id', string="Delivery IDs")
    delivery_id = fields.Char(string="Delivery ID", compute='_compute_delivery_id', search='_search_delivery_id', store=False)
    
    @api.depends('delivery_ids')
    def _compute_delivery_id(self):
        for order in self:
            # Get all delivery pickings for this order
            pickings = order.delivery_ids
            # Collect all delivery IDs (prioritize delivery_id, fallback to shipsy_reference_number)
            delivery_ids = []
            for picking in pickings:
                # Use delivery_id if available, otherwise use shipsy_reference_number
                delivery_id = picking.delivery_id or picking.shipsy_reference_number
                if delivery_id:
                    delivery_ids.append(delivery_id)
            
            # Join all delivery IDs with commas
            order.delivery_id = ', '.join(delivery_ids) if delivery_ids else False
    
    @api.model
    def _search_delivery_id(self, operator, value):
        # Search in both delivery_id and shipsy_reference_number fields
        pickings = self.env['stock.picking'].search([
            '|',
            ('delivery_id', operator, value),
            ('shipsy_reference_number', operator, value)
        ])
        return [('id', 'in', pickings.mapped('sale_id').ids)]
    def action_cancel_custom(self):
        """Override the standard cancel method to show the wizard"""
        # If we're bypassing the wizard (coming from the wizard itself), call the super method
        if self.env.context.get('bypass_cancel_wizard'):
            return super(SaleOrder, self).action_cancel()
            
        # Otherwise, show the wizard
        return {
            'type': 'ir.actions.act_window',
            'name': _('Selectionnez le motif d\'annulation'),
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

    def action_cancel(self):
        """Override the standard cancel method to clear status2 field"""
        self.write({'status2': False})
        return super(SaleOrder, self).action_cancel()
    def _compute_customer_phone(self):
        for order in self:
            order.customr_phone = order.partner_id.phone or order.partner_id.mobile


    @api.depends('receipt_ids')
    def _compute_receipt_count(self):
        for order in self:
            # Only count receipts with picking type 'incoming'
            incoming_receipts = order.receipt_ids.filtered(lambda p: p.picking_type_id.code == 'incoming')
            order.receipt_count = len(incoming_receipts)

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to send WhatsApp message when sale order is created"""
        orders = super(SaleOrder, self).create(vals_list)
        
        # Send WhatsApp message for each created order
        for order in orders:
            order._send_quotation_whatsapp_message()
        
        return orders

    def action_confirm(self):
        # First handle standard confirmation to create initial deliveries
        res = super(SaleOrder, self).action_confirm()
        self.write({'status2': False})
        self.write({'cancel_reason': False})
        
        # After standard confirmation, handle separate deliveries for products with separate_delivery_per_unit enabled
        # This needs to run after super() because we need the initial deliveries to be created
        self._create_separate_deliveries()
        
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


    
    def _create_separate_deliveries(self):
        """
        Create separate deliveries for products that have separate_delivery_per_unit enabled.
        This method modifies existing delivery orders to split quantities into separate deliveries.
        """
        # First check if any order lines have products with separate_delivery_per_unit enabled
        has_separate_delivery_products = False
        for line in self.order_line:
            product_tmpl = line.product_id.product_tmpl_id
            if product_tmpl.separate_delivery_per_unit and line.product_uom_qty > 1:
                has_separate_delivery_products = True
                break
                
        if not has_separate_delivery_products:
            return
            
        # Get all delivery pickings for this sale order
        delivery_pickings = self.picking_ids.filtered(lambda p: p.picking_type_id.code == 'outgoing')
        
        if not delivery_pickings:
            # No deliveries created yet, nothing to do
            return
            
        for picking in delivery_pickings:
            moves_to_split = []
            
            # Find moves that need to be split (products with separate_delivery_per_unit = True)
            for move in picking.move_ids_without_package:
                # Double check with the product template directly to ensure we have the right value
                product_tmpl = self.env['product.template'].browse(move.product_id.product_tmpl_id.id)
                if product_tmpl.separate_delivery_per_unit and move.product_uom_qty > 1:
                    moves_to_split.append(move)
            
            # Process each move that needs splitting
            for move in moves_to_split:
                original_qty = int(move.product_uom_qty)
                
                # Update the original move to have quantity 1
                move.write({'product_uom_qty': 1})
                move.write({'quantity': 1})
                
                # Create separate pickings for the remaining quantities
                for i in range(1, original_qty):
                    # Create a new picking for each additional unit
                    new_picking_vals = {
                        'picking_type_id': picking.picking_type_id.id,
                        'location_id': picking.location_id.id,
                        'location_dest_id': picking.location_dest_id.id,
                        'origin': picking.origin,
                        'partner_id': picking.partner_id.id,
                        'sale_id': self.id,
                        'move_ids_without_package': [(0, 0, {
                            'product_id': move.product_id.id,
                            'product_uom_qty': 1,
                            'product_uom': move.product_uom.id,
                            'name': move.name,
                            'location_id': picking.location_id.id,
                            'location_dest_id': picking.location_dest_id.id,
                            'sale_line_id': move.sale_line_id.id if move.sale_line_id else False,
                            'procure_method': 'make_to_stock',
                            'state': 'draft',
                        })]
                    }
                    # Create the new picking
                    new_picking = self.env['stock.picking'].create(new_picking_vals)
                    
                    # Explicitly set the sale_id field to ensure the relationship is properly established
                    new_picking.write({'sale_id': self.id})
                                        
                    # Confirm the new picking to make it ready
                    if new_picking.state == 'draft':
                        new_picking.action_confirm()
    
    def _send_quotation_whatsapp_message(self):
        """
        Send WhatsApp message to customer when sale order is confirmed using the configured template.
        """
        try:
            # Get the WhatsApp template from settings
            template_id = int(self.env['ir.config_parameter'].sudo().get_param('custom_features.quotation_whatsapp_template') or 0)
            
            if not template_id:
                _logger.info("No quotation WhatsApp template configured in settings")
                return
            
            template = self.env['whatsapp.template'].browse(template_id)
            if not template.exists():
                _logger.warning("Configured quotation WhatsApp template (ID: %s) does not exist", template_id)
                return
            
            # Check if customer has a phone number
            phone_number = self.partner_id.mobile or self.partner_id.phone
            if not phone_number:
                _logger.info("Customer %s has no phone number, skipping WhatsApp message", self.partner_id.name)
                return
            
            # Create WhatsApp composer to send the message
            composer = self.env['whatsapp.composer'].create({
                'res_model': 'sale.order',
                'res_ids': str([self.id]),
                'wa_template_id': template.id,
                'phone': phone_number,
            })
            
            # Send the message
            composer._send_whatsapp_template()
            _logger.info("WhatsApp quotation message sent to customer %s for order %s", self.partner_id.name, self.name)
            
        except Exception as e:
            _logger.error("Failed to send WhatsApp quotation message for order %s: %s", self.name, str(e))
