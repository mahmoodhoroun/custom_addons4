{
    'name': 'Shipsy Shipping Connector',
    'version': '1.0',
    'category': 'Inventory/Delivery',
    'summary': 'Integration with Shipsy shipping services',
    'description': """
        This module provides integration with Shipsy shipping services.
        It allows you to connect with Shipsy API and manage shipments.
    """,
    'author': 'Odoo',
    'depends': ['stock', 'delivery'],
    'data': [
        'security/ir.model.access.csv',
        'views/shipsy_connector_views.xml',
        'views/shipsy_pickup_wizard_view.xml',
        'views/stock_picking_view.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
