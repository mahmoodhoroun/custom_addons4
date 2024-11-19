from odoo import models, fields, api

class MrpBomAddition(models.Model):
    _name = 'mrp.bom.addition'
    _description = 'Additional Products for Kit'

    product_id = fields.Many2one('product.product', string="Product", required=True)
    quantity = fields.Float(string="Quantity", required=True, default=1.0)
    bom_id = fields.Many2one('mrp.bom', string="Bill of Materials", ondelete='cascade')

class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    receive_products = fields.Many2one('stock.location', string='Receive Products')
    from_products = fields.Many2one(
        'stock.location',
        string='From',
        default=lambda self: self._get_default_partner_location()
    )

    @api.model
    def _get_default_partner_location(self):
        """
        Fetch the default Partner Location (typically 'stock.stock_location_customers').
        """
        return self.env.ref('stock.stock_location_customers', raise_if_not_found=False)
    additional_product_ids = fields.One2many(
        'mrp.bom.addition', 'bom_id', string="Additional Products"
    )


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _action_done(self, **kwargs):
        res = super(StockMove, self)._action_done(**kwargs)

        # Process additional products for kits
        for move in self.filtered(lambda m: m.bom_line_id and m.bom_line_id.bom_id.type == 'phantom'):
            bom = move.bom_line_id.bom_id
            if hasattr(bom, 'additional_product_ids'):
                for addition in bom.additional_product_ids:
                    self.env['stock.move'].create({
                        'product_id': addition.product_id.id,
                        'product_uom_qty': addition.quantity,
                        'location_id': move.location_dest_id.id,
                        'location_dest_id': move.location_id.id,  # Adding to stock
                        'state': 'done',
                        'name': addition.product_id.display_name or 'Stock Move for Additional Product',
                    })._action_done(**kwargs)

        return res