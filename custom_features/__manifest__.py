{
    'name': 'Custom Feature',
    'version': '1.0',
    'depends': ['base', 'stock', 'sale', 'purchase', 'product', 'shipping_integration', 'shipsy_shipping_connector'],  # Include other dependencies as needed
    'data': [
        # Add your XML files here if any
        'security/ir.model.access.csv',
        'views/report_sale_order.xml',
        'views/report_templates.xml',
        'views/report_invoice.xml',
        'views/res_partner_inherit.xml',
        'views/purchase_order_template.xml',
        'views/mrp_bom_addition_view.xml',
        'views/sale_order_view.xml',
        'views/stock_picking_view.xml',
        'views/product_template_view.xml',
        'wizards/sale_order_cancel_confirm_view.xml',
        'wizards/invoice_confirm_wizard_view.xml',
        'views/account_move_view.xml',
        'reports/picking_labels.xml',
    ],
    'installable': True,
    'application': True,
}