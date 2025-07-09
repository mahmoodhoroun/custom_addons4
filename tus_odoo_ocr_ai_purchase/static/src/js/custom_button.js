/** @odoo-module */
import { ListController } from "@web/views/list/list_controller";
import { registry } from '@web/core/registry';
import { listView } from '@web/views/list/list_view';
import { useService } from "@web/core/utils/hooks";

export class PurchaseListController extends ListController {
   setup() {
       super.setup();
       this.orm = useService('orm');
       this.actionService = useService('action');
       this.notification = useService('notification');
   }

   async onClickOCRPurchase() {
       debugger;
       const active_model = this.props.resModel;

       console.log('Active MOdel',active_model)
       try {
           const result = await this.orm.call(
               'purchase.order',
               'check_active_boolean_purchase',
               [active_model]
           );

           if (result.active) {
               await this.actionService.doAction({
                  type: 'ir.actions.act_window',
                  res_model: 'import.via.ocr',
                  name: 'Import From OCR',
                  view_mode: 'form',
                  views: [[false, 'form']],
                  target: 'new',
                  context: {
                      'active_model': active_model,
                      'record_id': result.record_id,
                  },
               });
           } else {
               this.notification.add(('We are unable to find any configuration for ' + active_model), {
                   type: 'danger',
               });
           }
       } catch (error) {
           console.error('Error during RPC call:', error);
           this.notification.add('Error during RPC call: ' + error.message, {
               type: 'danger',
           });
       }
   }
}

registry.category("views").add("ocr_button_purchase", {
   ...listView,
   Controller: PurchaseListController,
   buttonTemplate: "button_purchase.ListView.Buttons",
});
