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
{
    'name': 'Odoo WooCommerce Connector',
    'version': '17.0.2.0.1',
    'category': 'Ecommerce',
    'summary': 'Odoo WooCommerce Connector V17, WooCommerce, WooCommerce Odoo Connector, WooCommerce Connector, woocommerce, odoo17, Odoo Apps, Connector, Integration,ecommerce',
    'description': 'Effortlessly sync customers, products, and orders in '
                   'real-time between Odoo and WooCommerce with our powerful '
                   'connector. Streamline your workflow with seamless imports '
                   'from WooCommerce to Odoo and simplify exports for a '
                   'smooth data flow. Optimize synchronization using queue '
                   'jobs, overcoming challenges and ensuring an efficient, '
                   'uninterrupted business workflow. Elevate your '
                   'coordination and responsiveness with instant '
                   'notifications for a seamless integration experience.',
    'author': 'Cybrosys Techno Solutions',
    'maintainer': 'Cybrosys Techno Solutions',
    'company': 'Cybrosys Techno Solutions',
    'website': 'https://www.cybrosys.com',
    'depends': ['website_sale', 'stock', 'sale_management', 'account',
                'sale_stock'],
    'data': [
        'data/woo_commerce_data.xml',
        'data/ir_action_data.xml',
        'data/ir_cron_data.xml',
        'security/ir.model.access.csv',
        'views/woo_logs_views.xml',
        'views/woo_commerce_instance_views.xml',
        'views/product_product_views.xml',
        'views/res_partner_views.xml',
        'views/sale_order_views.xml',
        'views/account_tax_views.xml',
        'views/job_cron_views.xml',
        'views/product_category_views.xml',
        'views/product_attribute_views.xml',
        'wizard/woo_update_views.xml',
        'wizard/woo_operation_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'woo_commerce/static/src/xml/dashboard.xml',
            'woo_commerce/static/src/css/dashboard.css',
            'woo_commerce/static/src/js/lib/Chart.bundle.js',
            'woo_commerce/static/src/js/dashboard.js',
        ],
    },
    'images': ['static/description/banner.png'],
    "external_dependencies": {"python": ["WooCommerce"]},
    'license': 'OPL-1',
    'price': 59,
    'currency': 'EUR',
    'installable': True,
    'application': True,
    'auto_install': False,
}
