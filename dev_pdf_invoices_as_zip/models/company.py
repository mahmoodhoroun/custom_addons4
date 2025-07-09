# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle
#
##############################################################################

from odoo import models, fields


class Company(models.Model):
    _inherit = 'res.company'

    directory_path = fields.Char(string='Directory', help='Specify the path of folder in which you want to store reports of invoices/bills')
    split_by = fields.Integer(string='Split By', help='Specify number, Such as if you are going to download pdf reports of 4\
     invoices/Bills and specified 2 in Split By then 2 zip files will be created at configured location, and each zip file will\
      contain 2 pdf reports of invoices/bills')

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
