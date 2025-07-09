# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Odoo OCR Using AI Base',
    'version': '17.0.2.0.0',
    'summary': 'Odoo OCR Using AI Base is an innovative module that integrates Optical Character Recognition (OCR) technology powered by artificial intelligence (AI) into the Odoo ERP system. This module streamlines data entry processes, enhances accuracy, and improves operational efficiency by automatically extracting and digitizing text from scanned documents, images, and PDFs.',
    'sequence': 10,
    'description': """ 
        Odoo OCR Using AI Base is an innovative module that integrates Optical Character Recognition (OCR) technology powered by artificial intelligence (AI) into the Odoo ERP system. This module streamlines data entry processes, enhances accuracy, and improves operational efficiency by automatically extracting and digitizing text from scanned documents, images, and PDFs.
        Odoo OCR AI
        Odoo Optical Character Recognition
        AI-based OCR in Odoo
        Odoo OCR integration
        Odoo AI OCR module
        Automated OCR Odoo
        Odoo OCR document processing
        Odoo AI text recognition
        Odoo OCR invoice scanning
        Odoo OCR AI implementation
        OCR automation with Odoo
        Intelligent OCR Odoo
        Odoo OCR solution
        Odoo AI document scanning
        AI OCR Odoo application
        Odoo machine learning OCR
        Odoo OCR AI technology
        Odoo document AI OCR
        Odoo OCR workflow automation
        Odoo AI OCR customization
        Odoo OCR
        AI Invoice Processing
        Invoice OCR
        Optical Character Recognition
        AI-Powered OCR
        Invoice Automation
        Smart Invoice Scanning
        Odoo Invoice Management
        Automated Invoice Data Extraction
        OCR AI Integration
        Invoice Recognition
        AI Document Processing
        OCR for Accounting
        Intelligent Invoice Processing
        AI-Driven OCR
        Invoice Data Capture
        Odoo AI Module
        OCR Invoice Automation
        Digital Invoice Processing
        Machine Learning OCR
     """,
    'category': 'Tools',
    'website': "https://www.techultrasolutions.com",
    "author": "TechUltra Solutions Private Limited",
    "company": "TechUltra Solutions Private Limited",
    'live_test_url': 'https://ai.fynix.app/',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        # 'security/security.xml',
        'wizards/import_via_ocr_wizard_view.xml',
        'views/odoo_ocr_ai_config_views.xml',
        'views/odoo_ocr_api_config_view.xml',
    ],
    "images": ["static/description/main_banner.gif"],
    'demo': [],
    'installable': True,
    'application': True,
    'license': 'OPL-1',
}
