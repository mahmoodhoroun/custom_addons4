# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle
#
##############################################################################

{
    'name': 'Download Invoices Reports as Zip File-Export Invoice zip',
    'version': '17.0.1.0',
    'sequence': 1,
    'category': 'Accounting',
    'description':
        """
This Module add below functionality into odoo

        1.Download pdf reports of Invoices as zip file at desired location in your system\n
        2.Set path of desired directory into Invoicing > Settings > Download Invoices as Zip\n
        3.You can filter downloaded and not downloaded invoices from search filter\n
        4.Note : Only user with 'Allow to Download Invoices Report(pdf) as Zip' right can configure directory path and download invoices
        
        Odoo app Transfer Invoices files in Zip file on given location, download pdf zip, export invoice zip, export multiple pdf invoice, Invoice bulk download export, export invoice file invoice reports zip, export invoice pdf zip

    """,
    'summary': 'Odoo app Transfer Invoices files in Zip file on given location, download pdf zip, export invoice zip, export multiple pdf invoice, Invoice bulk download export, export invoice file invoice reports zip, export invoice pdf zip',
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'views/res_config_settings_views.xml',
        'views/account_invoice_views.xml',
        'wizard/download_invoice_reports_views.xml'
    ],
    'demo': [],
    'test': [],
    'css': [],
    'qweb': [],
    'js': [],
    'images': ['images/main_screenshot.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
    
    # author and support Details =============#
    'author': 'DevIntelle Consulting Service Pvt.Ltd',
    'website': 'https://www.devintellecs.com',    
    'maintainer': 'DevIntelle Consulting Service Pvt.Ltd', 
    'support': 'devintelle@gmail.com',
    'price':19.0,
    'currency':'EUR',
    #'live_test_url':'https://youtu.be/A5kEBboAh_k',
    'pre_init_hook' :'pre_init_check',
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
