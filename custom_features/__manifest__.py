{
    'name': 'Custom Feature',
    'version': '1.0',
    'depends': ['base', 'stock'],  # Include other dependencies as needed
    'data': [
        # Add your XML files here if any
        'views/report_sale_order.xml',
        'views/report_templates.xml',
        'views/report_invoice.xml',
    ],
    'installable': True,
    'application': True,
}