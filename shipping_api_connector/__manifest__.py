{
    'name': 'Shipping API Connector',
    'version': '17.0.1.0.0',
    'category': 'Inventory/Delivery',
    'summary': 'Connect Odoo with shipping company APIs',
    'description': """
        This module provides integration with shipping company APIs.
        Features include:
        - Configuration of shipping carriers and their API credentials
        - Sending shipping requests to carriers
        - Tracking shipments
        - Generating shipping labels
        - Managing shipping rates
    """,
    'author': 'Mahmood Haroun',
    'depends': [
        'base',
        'stock',
        'delivery',
        'sale',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/barid_ma_views.xml',
        'views/stock_picking_view.xml',
        'reports/paperformat.xml',
        'reports/barid_ma_label_report.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'shipping_api_connector/static/src/img/*',
        ],
    },

    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
