# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle
#
##############################################################################

from odoo import models, fields, _
from odoo.http import request
import os
import shutil
from odoo.exceptions import ValidationError
import base64


class DownloadInvoiceReports(models.TransientModel):
    _name = 'download.invoice.reports'
    _description="Invoice Report ZIP"

    def download_invoice_pdf_reports(self):
        active_ids = self._context.get('active_ids')
        invoice_ids = self.env['account.move'].browse(active_ids)
        if invoice_ids:
            directory = self.env.user.company_id.directory_path
            split_by = self.env.user.company_id.split_by
            if not directory:
                raise ValidationError(_('''Please configure Directory into Invoicing > Settings > Download Invoices as Zip'''))
            if not os.path.isdir(directory):
                raise ValidationError(_(''''%s' is does not seems to be a valid directory, please configure valid one''') % (directory))
            if any(inv.state in ['draft','cancel'] for inv in invoice_ids):
                raise ValidationError(_('''Please only select those Invoices/Bill which are Open or Paid'''))
            if any(inv.pdf_report_downloaded for inv in invoice_ids):
                raise ValidationError(_('''Please select only those invoices whose report is not downloaded'''))
            copy_dict = ''
            if self.download_also:
                copy_dict = directory + '/pdf_invoices_bills'
                os.mkdir(copy_dict)
            if split_by > 0:
                part_range = len(invoice_ids)/split_by
                part_range = round(part_range) + 1
                invoice_list = invoice_ids.ids
                invoice_list.sort()
                for part in range(part_range):
                    part_list = invoice_list[:int(split_by)]
                    part_list.sort()
                    if part_list:
                        invoice_list = invoice_list[int(split_by):]
                        invoice_list.sort()
                        part_invoice_ids = self.env['account.move'].browse(part_list)
                        if part_invoice_ids:
                            start = str(self.env['account.move'].browse(part_invoice_ids.ids[0]).name)
                            end = str(self.env['account.move'].browse(part_invoice_ids.ids[-1]).name)
                            zip_directory = directory + '/' + 'invoices_' + str(start.replace('/', '')) + '_' + str(end.replace('/', ''))
                            os.mkdir(zip_directory)
                            if self.single_page_invoices:
                                multi_invoices_file_name = 'invoices_' + str(start.replace('/', '')) + '_' + str(end.replace('/', ''))+ '.pdf'
                                with open(os.path.join(zip_directory, multi_invoices_file_name), "wb+") as f:
                                    pdf_files = self.env['ir.actions.report'].sudo()._render_qweb_pdf('account.account_invoices', part_invoice_ids.ids, data=False)[0]
                                    f.write(pdf_files)
                            else:
                                for invoice in part_invoice_ids:
                                    pdf_name = (invoice.name.replace('/', '')) + '.pdf'
                                    with open(os.path.join(zip_directory, pdf_name), "wb+") as f:
                                        pdf = self.env['ir.actions.report'].sudo()._render_qweb_pdf('account.account_invoices', [invoice.id], data=False)[0]
                                        f.write(pdf)
                            file = shutil.make_archive(zip_directory, 'zip', zip_directory)
                            if self.download_also and file and copy_dict:
                                shutil.copy(file, copy_dict)
                            shutil.rmtree(zip_directory)
                            for invoice in part_invoice_ids:
                                 invoice.pdf_report_downloaded = True

                if os.path.isdir(copy_dict):
                    download_file = shutil.make_archive(copy_dict, 'zip', copy_dict)
                    shutil.rmtree(copy_dict)
                    if download_file:
                        with open(download_file, 'rb') as f:
                            zip_file = f.read()
                        self.invoice_reports = base64.b64encode(zip_file)
                    os.remove(download_file)
                    form_id = self.env.ref('dev_pdf_invoices_as_zip.form_dev_pdf_invoices_as_zip_on_screen_report').id
                    return {'name': 'Download PDF Reports',
                            'type': 'ir.actions.act_window',
                            'view_mode': 'form',
                            'res_model': 'download.invoice.reports',
                            'views': [(form_id, 'form')],
                            'target': 'new',
                            'res_id': int(self.id),
                            }
            else:
                start = str(self.env['account.move'].browse(invoice_ids.ids[0]).name)
                end = str(self.env['account.move'].browse(invoice_ids.ids[-1]).name)
                zip_directory = directory + '/' + 'invoices_' + str(start.replace('/', '')) + '_' + str(end.replace('/', ''))
                os.mkdir(zip_directory)
                if self.single_page_invoices:
                    multi_invoices_file_name = 'invoices_' + str(start.replace('/', '')) + '_' + str(end.replace('/', ''))
                    with open(os.path.join(zip_directory, multi_invoices_file_name), "wb+") as f:
                        pdf_files = request.env.ref('account.account_invoices').sudo()._render(invoice_ids.ids, data=False)[0]
                        f.write(pdf_files)
                else:
                    for invoice in invoice_ids:
                        pdf_name = (invoice.name.replace('/', '')) + '.pdf'
                        with open(os.path.join(zip_directory, pdf_name), "wb+") as f:
                            pdf = request.env.ref('account.account_invoices').sudo()._render([invoice.id])[0]
                            f.write(pdf)
                file = shutil.make_archive(zip_directory, 'zip', zip_directory)
                if self.download_also and file and copy_dict:
                    shutil.copy(file, copy_dict)
                shutil.rmtree(zip_directory)
                for invoice in invoice_ids:
                     invoice.pdf_report_downloaded = True
                if os.path.isdir(copy_dict):
                    download_file = shutil.make_archive(copy_dict, 'zip', copy_dict)
                    shutil.rmtree(copy_dict)
                    if download_file:
                        with open(download_file, 'rb') as f:
                            zip_file = f.read()
                        self.invoice_reports = base64.b64encode(zip_file)
                    os.remove(download_file)
                    form_id = self.env.ref('dev_pdf_invoices_as_zip.form_dev_pdf_invoices_as_zip_on_screen_report').id
                    return {'name': 'Download PDF Reports',
                            'type': 'ir.actions.act_window',
                            'view_mode': 'form',
                            'res_model': 'download.invoice.reports',
                            'views': [(form_id, 'form')],
                            'target': 'new',
                            'res_id': int(self.id),
                            }

    download_also = fields.Boolean(string='Download on Screen', help='If true, then reports of invoices/bills will be downloaded at configured location as usual and it will allows you to download those reports from screen also')
    single_page_invoices = fields.Boolean(string='Invoices in One Page', help='If true, then each zip file will contains only one pdf file and that pdf file will contain multiple reports on invoices/bills, in short it will not create separate pdf report for each invoice/bill')
    invoice_reports = fields.Binary(string='Invoice/Bill PDF Zip Download')

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
