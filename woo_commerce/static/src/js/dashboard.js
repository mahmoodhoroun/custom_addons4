/** @odoo-module **/
const { Component, useState, onWillStart } = owl;
import { registry } from "@web/core/registry";
import { useService, useListener } from "@web/core/utils/hooks";
import { session } from "@web/session";
import { loadBundle } from "@web/core/assets";
import { _t } from "@web/core/l10n/translation";
const actionRegistry = registry.category("actions");

class WooDashBoard extends Component {
    async setup() {
        super.setup(...arguments);
        this.state = useState({
             order_outputs: [],
             product_outputs: [],
        });
        this.rpc = useService('rpc');
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.render_tile();
        this.render_orders_table();
        this.render_products();
        this.render_product_category();
        this.render_instance();
        this.tile_graphs();
        $('oe_background_grey').addClass('d-none');

           onWillStart(async () => {
            let result = await $.when(loadBundle(this));
            return result;
            });
        }

        render_tile() {
            var def1 =  this.orm.call('sale.order','get_tile_details',[]
            ).then((result) => {
               var instance_count = result.instance
               var products_count = result.products
               var orders_count = result.orders
               var customers_count = result.partners
               $('.instance_right').append('<div class="count-container">'+instance_count+'</div>');
               $('.product_right').append('<div class="count-container">'+products_count+'</div>');
               $('.partner_right').append('<div class="count-container">'+customers_count+'</div>');
               $('.order_right').append('<div class="count-container">'+orders_count+'</div>');
            });
          }

        render_orders_table(){
            var self = this
            var def1 =  this.orm.call('sale.order','get_orders',[]
            ).then((result) =>  {
            self.state.order_outputs = result;
            });
          }

        render_products(){
            var self = this
            this.orm.call('product.template', 'get_product_graph',[]
            ).then((result)  => {
                self.state.product_outputs = result;
            });
          }

          render_product_category(){
            this.orm.call('product.category','get_product_category_graph',[]
            ).then((result) => {
                var ctx = $("#category_canvas");
                var myChart = new Chart(ctx, {
                    type: 'doughnut',
                    data: {
                        labels: result.categories_name,//x axis
                        datasets: [{
                            label: 'Count', // Name the series
                            data: result.products_count, // Specify the data values array
                            backgroundColor: [
                                "#003f5c",
                                "#2f4b7c",
                                "#f95d6a",
                                "#665191",
                                "#d45087",
                                "#ff7c43",
                                "#ffa600",
                                "#a05195",
                                "#6d5c16",
                                "#dc3545",
                                "#1995ad",
                                "#317773",
                                "#1995ad",
                                "#9a9eab",
                                "#007bff",
                                "#20c997",
                                "#BCC6CC",
                                "#4682B4",
                                 "#7B68EE",
                                "#FF007F",
                                "#800020",
                                "#FFEF00",
                                "#FF5A36",
                                "#082567",
                            ],
                            borderColor: [
                                "#003f5c",
                                "#2f4b7c",
                                "#f95d6a",
                                "#665191",
                                "#d45087",
                                "#ff7c43",
                                "#ffa600",
                                "#a05195",
                                "#6d5c16",
                                "#dc3545",
                                "#1995ad",
                                "#317773",
                                "#1995ad",
                                "#9a9eab",
                                "#007bff",
                                "#20c997",
                            ],

                            barPercentage: 0.5,
                            barThickness: 6,
                            maxBarThickness: 8,
                            minBarLength: 0,
                            borderWidth: 1, // Specify bar border width
                            type: 'doughnut', // Set this data to a line chart
                            fill: false
                        }]
                    },
                    options: {
                        scales: {
                            y: {
                                beginAtZero: true
                            },
                        },
                        responsive: true, // Instruct chart js to respond nicely.
                        maintainAspectRatio: false, // Add to prevent default behaviour of full-width/height
                    }//                                borderColor: '#66aecf',
                });
            });
      }

      render_instance(){
        this.orm.call('woo.commerce.instance',"get_instance_graph",[]
        ).then((result) => {
            var ctx = $("#customers_canvas");
            var myChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: result.instance_name,//x axis
                    datasets: [
                            {
                                label: "Products",
                                backgroundColor: "#A7226E",
                                data: result.product_len
                            },
                            {
                                label: "Customers",
                                backgroundColor: "#EC2049",
                                data: result.customer_len
                            },
                            {
                                label: "Orders",
                                backgroundColor: "#2F9599",
                                data: result.order_len
                            }
                        ]
                },
                options: {
                    scales: {
                        y: {
                            beginAtZero: true
                        },
                    },
                    responsive: true, // Instruct chart js to respond nicely.
                    maintainAspectRatio: false, // Add to prevent default behaviour of full-width/height
                }//                                borderColor: '#66aecf',
            });
        });
      }

      tile_graphs(){
            var dataBar = {
          labels: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug"],
          datasets: [{
            label: 'Customers',
            data: [5, 10, 15, 12, 10, 8, 6, 4],
            backgroundColor: [
              '#dee5ef',
              '#dee5ef',
              '#dee5ef',
              '#dee5ef',
              '#fc381d',
              '#dee5ef',
              '#dee5ef',
              '#dee5ef',
            ],
            borderColor: [
              '#dee5ef',
              '#dee5ef',
              '#dee5ef',
              '#dee5ef',
              '#fc381d',
              '#dee5ef',
              '#dee5ef',
              '#dee5ef',
            ],
            borderWidth: 1,
            fill: false
          }]
        };
        var optionsBar = {
          scales: {
            yAxes: [{
              ticks: {
                beginAtZero: true,
                display: false,

              },
              gridLines: {
                display: false,
                drawBorder: false
              }
            }],
            xAxes: [{
              ticks: {
                beginAtZero: true,
                display: false,
              },
              gridLines: {
                display: false,
                drawBorder: false
              }
            }]
          },
          legend: {
            display: false
          },
          elements: {
            point: {
              radius: 0
            }
          },
          tooltips: {
            enabled: false
          }

        };
        var barChartCanvas = $("#customers");
          // This will get the first returned node in the jQuery collection.
          var ctx = $("#customers");
          ctx.height = 60;
          var barChart = new Chart(barChartCanvas, {
                type: 'bar',
                data: dataBar,
                options: optionsBar
              });
        }

      onclick_instance(ev) {
            ev.stopPropagation();
            var options = {
                on_reverse_breadcrumb: this.on_reverse_breadcrumb,
            };
            this.actionService.doAction({
                name: _t("Instance"),
                type: 'ir.actions.act_window',
                res_model: 'woo.commerce.instance',
                view_mode: 'tree,form,calendar',
                views: [[false, 'list'],[false, 'form']],
                target: 'current',
            }, options)
        }

      onclick_product(ev) {
            ev.stopPropagation();
            var options = {
                on_reverse_breadcrumb: this.on_reverse_breadcrumb,
            };
            this.actionService.doAction({
                name: _t("Product"),
                type: 'ir.actions.act_window',
                res_model: 'product.template',
                view_mode: 'tree,form,calendar',
                views: [[false, 'list'],[false, 'form']],
                domain: [['woo_id', '!=', false]],
                target: 'current',
            }, options)
        }

      onclick_customer(ev) {
            ev.stopPropagation();
            var options = {
                on_reverse_breadcrumb: this.on_reverse_breadcrumb,
            };
            this.actionService.doAction({
                name: _t("Customers"),
                type: 'ir.actions.act_window',
                res_model: 'res.partner',
                view_mode: 'tree,form,calendar',
                views: [[false, 'list'],[false, 'form']],
                domain: [['woo_id', '!=', false]],
                target: 'current',
            }, options)
        }

      onclick_orders(ev) {
            ev.stopPropagation();

            var options = {
                on_reverse_breadcrumb: this.on_reverse_breadcrumb,
            };
            this.actionService.doAction({
                name: _t("Orders"),
                type: 'ir.actions.act_window',
                res_model: 'sale.order',
                view_mode: 'tree,form,calendar',
                views: [[false, 'list'],[false, 'form']],
                domain: [['woo_id', '!=', false]],
                target: 'current',
            }, options)
        }

        onclick_product_search() {
            var input, filter, table, tr, td, i, txtValue;
              input = document.getElementById("product_search");
              filter = input.value.toUpperCase();
              table = document.getElementById("product_table");
              tr = table.getElementsByTagName("tr");
              for (i = 0; i < tr.length; i++) {
                td = tr[i].getElementsByTagName("td")[0];
                if (td) {
                  txtValue = td.textContent || td.innerText;
                  if (txtValue.toUpperCase().indexOf(filter) > -1) {
                    tr[i].style.display = "";
                  } else {
                    tr[i].style.display = "none";
                  }
                }
              }
        }

        onclick_order_search() {
            var input, filter, table, tr, td, i, txtValue;
              input = document.getElementById("order_search");
              filter = input.value.toUpperCase();
              table = document.getElementById("orders_table");
              tr = table.getElementsByTagName("tr");
              for (i = 0; i < tr.length; i++) {
                td = tr[i].getElementsByTagName("td")[0];
                if (td) {
                  txtValue = td.textContent || td.innerText;
                  if (txtValue.toUpperCase().indexOf(filter) > -1) {
                    tr[i].style.display = "";
                  } else {
                    tr[i].style.display = "none";
                  }
                }
              }
        }
        onclick_order_row(ev){
            var order_id = ev.target.innerHTML;
            var options = {
                on_reverse_breadcrumb: this.on_reverse_breadcrumb,
            };
            this.actionService.doAction({
                name: _t("Order"),
                type: 'ir.actions.act_window',
                res_model: 'sale.order',
                view_mode: 'form',
                views: [[false, 'list'],[false, 'form']],
                domain: [['name', '=', order_id]],
                target: 'current',
            }, options)
        }
}
WooDashBoard.template = 'Woocommercedashboard';
actionRegistry.add("woocommerce_dashboard_tag", WooDashBoard);
