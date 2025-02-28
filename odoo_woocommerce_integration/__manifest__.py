{  
    'name': 'Odoo WooCommerce Integration',  
    'version': '1.0',  
    'category': 'Sales',  
    'summary': 'Integrate Odoo with WooCommerce',  
    'description': 'This module allows users to upload products from Odoo to WooCommerce.',  
    'author': 'Mahmood Haroun',
    'depends': ['base', 'product', 'sale', 'component', 'bad_connector_woocommerce'],  
    'data': [  
        'security/ir.model.access.csv',
        'views/product_views.xml',
    ],  
    'installable': True,  
    'application': True,  
    'auto_install': False,
}
