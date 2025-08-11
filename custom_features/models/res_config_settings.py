# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    quotation_whatsapp_template = fields.Many2one(
        'whatsapp.template',
        string='Quotation WhatsApp Template',
        config_parameter='custom_features.quotation_whatsapp_template',
        help='WhatsApp template for quotation notifications'
    )
    
    cathedis_whatsapp_template = fields.Many2one(
        'whatsapp.template',
        string='Cathedis WhatsApp Template',
        config_parameter='custom_features.cathedis_whatsapp_template',
        help='WhatsApp template for Cathedis notifications'
    )
    
    chronodiali_whatsapp_template = fields.Many2one(
        'whatsapp.template',
        string='Chronodiali WhatsApp Template', 
        config_parameter='custom_features.chronodiali_whatsapp_template',
        help='WhatsApp template for Chronodiali notifications'
    )
