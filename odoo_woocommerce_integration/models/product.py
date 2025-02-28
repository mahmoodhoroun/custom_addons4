from odoo import models, fields, api
from odoo.addons.bad_connector_woocommerce.components.backend_adapter import WooAPI, WooLocation
import logging
import requests
import json

_logger = logging.getLogger(__name__)

class ProductCategory(models.Model):
    _inherit = 'product.category'

    woo_bind_ids = fields.One2many(
        comodel_name='woo.product.category',
        inverse_name='odoo_id',
        string='WooCommerce Bindings',
        context={'active_test': False},
    )

    def _get_or_create_woo_category(self, woo_backend):
        """Get or create WooCommerce category"""
        self.ensure_one()
        if not self.woo_bind_ids:
            # Create WooCommerce binding
            self.env['woo.product.category'].create({
                'backend_id': woo_backend.id,
                'odoo_id': self.id,
                'name': self.name,
                'description': self.name,
            })
        return self.woo_bind_ids[0]

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    woo_bind_ids = fields.One2many(
        comodel_name='woo.product.template',
        inverse_name='odoo_id',
        string='WooCommerce Bindings',
        context={'active_test': False},
    )

    @api.model
    def get_product_by_sku(self, sku):
        """Find product by SKU"""
        return self.env['product.product'].search([('default_code', '=', sku)], limit=1)

    @api.model
    def get_or_create_product(self, woo_data, woo_backend):
        """Get existing product or create new one"""
        product = False
        
        # Try to find by WooCommerce binding first
        woo_product = self.env['woo.product.product'].search([
            ('backend_id', '=', woo_backend.id),
            ('external_id', '=', str(woo_data['id']))
        ], limit=1)
        if woo_product:
            product = woo_product.odoo_id
            
        # If no product found by binding, try to find by SKU
        if not product and woo_data.get('sku'):
            product = self.get_product_by_sku(woo_data['sku'])
            if product:
                # Create WooCommerce binding if product found by SKU
                existing_binding = self.env['woo.product.product'].search([
                    ('backend_id', '=', woo_backend.id),
                    ('odoo_id', '=', product.id)
                ], limit=1)
                if not existing_binding:
                    self.env['woo.product.product'].create({
                        'backend_id': woo_backend.id,
                        'odoo_id': product.id,
                        'external_id': str(woo_data['id']),
                        'woo_product_name': woo_data['name'],
                        'status': woo_data.get('status', 'publish'),
                        'tax_status': woo_data.get('tax_status', 'taxable'),
                        'stock_status': woo_data.get('stock_status', 'instock'),
                    })

        # If still no product found, create new one
        if not product:
            product_vals = {
                'name': woo_data['name'],
                'default_code': woo_data.get('sku', ''),
                'description': woo_data.get('description', ''),
                'description_sale': woo_data.get('short_description', ''),
                'type': 'product',
                'list_price': float(woo_data.get('regular_price', 0.0)),
            }
            product = self.env['product.product'].create(product_vals)

            # Create WooCommerce binding for new product
            self.env['woo.product.product'].create({
                'backend_id': woo_backend.id,
                'odoo_id': product.id,
                'external_id': str(woo_data['id']),
                'woo_product_name': woo_data['name'],
                'status': woo_data.get('status', 'publish'),
                'tax_status': woo_data.get('tax_status', 'taxable'),
                'stock_status': woo_data.get('stock_status', 'instock'),
            })
        
        return product

    def action_upload_to_woocommerce(self):
        """Upload product to WooCommerce"""
        for record in self:
            # Check if product already has a WooCommerce binding
            if record.woo_bind_ids:
                woo_product = record.woo_bind_ids[0]
                _logger.info('Product %s already has WooCommerce binding: %s', record.name, woo_product.external_id)
                return self._update_woo_product(woo_product)
            
            # Get WooCommerce configuration
            woo_backend = self.env['woo.backend'].search([], limit=1)
            if not woo_backend:
                raise models.UserError('WooCommerce configuration not found')

            # Create WooLocation instance
            location = WooLocation(
                location=woo_backend.location,
                client_id=woo_backend.client_id,
                client_secret=woo_backend.client_secret,
                version=woo_backend.version,
                test_mode=woo_backend.test_mode
            )

            # Create WooAPI instance
            with WooAPI(location) as wcapi:
                # Prepare product data
                data = {
                    'name': record.name,
                    'type': 'simple',
                    'regular_price': str(record.list_price),
                    'description': record.description_sale or '',
                    'short_description': record.description or '',
                    'sku': record.default_code or '',
                    'manage_stock': True,
                    'stock_quantity': int(record.qty_available),
                    'status': 'publish'
                }

                # Add categories if available
                if record.categ_id:
                    woo_category = record.categ_id._get_or_create_woo_category(woo_backend)
                    if not woo_category.external_id:
                        # Create category in WooCommerce
                        category_data = {
                            'name': record.categ_id.name,
                            'description': record.categ_id.name,
                        }
                        if record.categ_id.parent_id:
                            parent_woo_category = record.categ_id.parent_id._get_or_create_woo_category(woo_backend)
                            if parent_woo_category.external_id:
                                category_data['parent'] = parent_woo_category.external_id
                        
                        category_result = wcapi.call('products/categories', category_data, http_method='POST')
                        if category_result and isinstance(category_result, dict) and 'id' in category_result:
                            woo_category.external_id = str(category_result['id'])
                        else:
                            _logger.warning('Failed to create category in WooCommerce: %s', category_result)
                    
                    if woo_category.external_id:
                        data['categories'] = [{'id': woo_category.external_id}]

                try:
                    _logger.info('Creating product in WooCommerce: %s', data)
                    result = wcapi.call('products', data, http_method='POST')
                    _logger.info('WooCommerce API Response: %s', result)

                    if result and isinstance(result, dict) and 'id' in result:
                        # Create WooCommerce template binding
                        woo_product = self.env['woo.product.template'].create({
                            'backend_id': woo_backend.id,
                            'odoo_id': record.id,
                            'external_id': str(result['id']),
                        })
                        
                        # Create WooCommerce product binding for each variant
                        for variant in record.product_variant_ids:
                            self.env['woo.product.product'].create({
                                'backend_id': woo_backend.id,
                                'odoo_id': variant.id,
                                'external_id': str(result['id']),  # For simple products, use the same ID
                                'woo_product_name': variant.name,
                                'status': result.get('status', 'publish'),
                                'tax_status': result.get('tax_status', 'taxable'),
                                'stock_status': result.get('stock_status', 'instock'),
                            })
                        
                        _logger.info('Created WooCommerce binding: %s', woo_product)
                        return woo_product
                    else:
                        raise models.UserError(f'Error creating product in WooCommerce: {result}')

                except Exception as e:
                    _logger.error('Error uploading product to WooCommerce: %s', str(e))
                    raise models.UserError(f'Error uploading product to WooCommerce: {str(e)}')

    def _update_woo_product(self, woo_product):
        """Update existing WooCommerce product"""
        woo_backend = woo_product.backend_id

        # Create WooLocation instance
        location = WooLocation(
            location=woo_backend.location,
            client_id=woo_backend.client_id,
            client_secret=woo_backend.client_secret,
            version=woo_backend.version,
            test_mode=woo_backend.test_mode
        )

        # Create WooAPI instance
        with WooAPI(location) as wcapi:
            data = {
                'name': self.name,
                'regular_price': str(self.list_price),
                'description': self.description_sale or '',
                'short_description': self.description or '',
                'sku': self.default_code or '',
                'manage_stock': True,
                'stock_quantity': int(self.qty_available),
            }

            # Add categories if available
            if self.categ_id:
                woo_category = self.categ_id._get_or_create_woo_category(woo_backend)
                if not woo_category.external_id:
                    # Create category in WooCommerce
                    category_data = {
                        'name': self.categ_id.name,
                        'description': self.categ_id.name,
                    }
                    if self.categ_id.parent_id:
                        parent_woo_category = self.categ_id.parent_id._get_or_create_woo_category(woo_backend)
                        if parent_woo_category.external_id:
                            category_data['parent'] = parent_woo_category.external_id
                    
                    category_result = wcapi.call('products/categories', category_data, http_method='POST')
                    if category_result and isinstance(category_result, dict) and 'id' in category_result:
                        woo_category.external_id = str(category_result['id'])
                    else:
                        _logger.warning('Failed to create category in WooCommerce: %s', category_result)
                
                if woo_category.external_id:
                    data['categories'] = [{'id': woo_category.external_id}]

            try:
                _logger.info('Updating product in WooCommerce: %s', data)
                result = wcapi.call(f"products/{woo_product.external_id}", data, http_method='PUT')
                _logger.info('WooCommerce API Response: %s', result)
                return woo_product
            except Exception as e:
                _logger.error('Error updating product in WooCommerce: %s', str(e))
                raise models.UserError(f'Error updating product in WooCommerce: {str(e)}')
