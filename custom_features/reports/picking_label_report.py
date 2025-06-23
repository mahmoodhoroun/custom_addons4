from odoo import models, api

class PickingLabelReport(models.AbstractModel):
    _name = 'report.custom_features.report_picking_labels'
    _description = 'Picking Label Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        # Get the pickings
        pickings = self.env['stock.picking'].browse(docids)
        
        # Mark all pickings as having their labels printed
        pickings.write({'is_label_printed': True})
        
        # Return the standard report values
        return {
            'doc_ids': docids,
            'doc_model': 'stock.picking',
            'docs': pickings,
        }
