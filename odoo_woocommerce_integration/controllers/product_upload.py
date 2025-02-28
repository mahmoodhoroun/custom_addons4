from odoo import http
import requests

class ProductUploadController(http.Controller):
    @http.route('/upload_product', type='json', auth='public', methods=['POST'])
    def upload_product(self, **kwargs):
        # استخراج بيانات المنتج من Odoo
        product_id = kwargs.get('product_id')
        product = http.request.env['product.template'].browse(product_id)

        if not product:
            return {'error': 'Product not found'}

        # قراءة بيانات الاعتماد من إعدادات WooCommerce
        woo_backend = http.request.env['woo.backend'].search([], limit=1)
        access_token = woo_backend.access_token if woo_backend else None
        url = woo_backend.location if woo_backend else None

        if not access_token or not url:
            return {'error': 'No access token or URL found'}

        # تحضير البيانات للرفع إلى WooCommerce
        data = {
            'name': product.name,
            'type': 'simple',
            'regular_price': str(product.list_price),
            'description': product.description,
            'images': [{'src': image.url for image in product.image_ids}],
        }

        # إجراء طلب API إلى WooCommerce
        api_url = f"{url}/wp-json/wc/v3/products"
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {access_token}'
        }

        response = requests.post(api_url, json=data, headers=headers)

        if response.status_code == 201:
            # تسجيل بيانات المنتج في Odoo
            response_data = response.json()
            product.write({
                'woo_product_id': response_data.get('id'),  # معرف المنتج في WooCommerce
                'woo_product_categ_ids': [(6, 0, response_data.get('categories', []))],  # فئات المنتج
            })
            return {'success': 'Product created successfully in WooCommerce'}
        else:
            return {'error': response.json()}
