# -*- coding: utf-8 -*-
###############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2024-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Anfas Faisal K (odoo@cybrosys.com)
#
#    This program is under the terms of the Odoo Proprietary License v1.0(OPL-1)
#    It is forbidden to publish, distribute, sublicense, or sell copies of the
#    Software or modified copies of the Software.
#
#    THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#    FITNESS FOR A PARTICULAR PURPOSE AND NON INFRINGEMENT. IN NO EVENT SHALL
#    THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,DAMAGES OR OTHER
#    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,ARISING
#    FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
#    DEALINGS IN THE SOFTWARE.
#
###############################################################################
from odoo import api, fields, models


class ProductProduct(models.Model):
    """Class for the inherited model product_product. Contains fields and
        methods related to Woocommerce products.
    """
    _inherit = 'product.product'

    woo_price = fields.Float(string="woo price", copy=False,
                             help='Price in WooCommerce')
    woo_var_id = fields.Char(string="Woo Variant ID", readonly=True,
                             copy=False, help='Variant Id in WooCommerce.')

    @api.depends('list_price', 'price_extra')
    @api.depends_context('uom')
    def _compute_product_lst_price(self):
        """Overriding the compute function of lst_price for changing variant
           price based on the woocommerce price."""
        for recd in self:
            product_id = self.env['product.template'].search(
                [('product_variant_ids', 'in', recd.id)])
            if not product_id.woo_variant_check:
                to_uom = None
                if 'uom' in self._context:
                    to_uom = self.env['uom.uom'].browse(self._context['uom'])
                for product in self:
                    if to_uom:
                        list_price = product.uom_id._compute_price(
                            product.list_price, to_uom)
                    else:
                        list_price = product.list_price
                    product.lst_price = list_price + product.price_extra
            else:
                if recd.woo_price == 0:
                    recd.lst_price = recd.product_tmpl_id.list_price
                else:
                    recd.lst_price = recd.woo_price
