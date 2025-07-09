# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd
#    (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle
#
##############################################################################

from odoo import models, fields, api


class AccountInvoice(models.Model):
    _inherit = 'account.move'

    pdf_report_downloaded = fields.Boolean(string='PDF Report Downloaded', copy=False)


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
