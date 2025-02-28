from odoo.tests import TransactionCase


class TestReturnPicking(TransactionCase):
    def setUp(self):
        """Inherit the method to setup the data #T7254"""
        super(TestReturnPicking, self).setUp()
        self.picking = self.env.ref("stock.outgoing_shipment_main_warehouse")

    def test_01_create_returns_with_reason(self):
        """New method to test the return_reason is written to stock.picking #T7254"""
        # Create and validate a stock.picking record #T7254
        picking = self.picking
        picking.button_validate()

        # Create a ReturnPicking wizard #T7254
        return_wizard = self.env["stock.return.picking"].create(
            {"picking_id": picking.id, "return_reason": "<p>Testing return reason</p>"}
        )

        # Call the _create_returns method #T7254
        new_picking_id, picking_type_id = return_wizard._create_returns()

        # Get the return picking #T7254
        new_picking = self.env["stock.picking"].browse(new_picking_id)
        # Check that the return_reason is correctly written to the
        # new stock.picking record #T7254
        self.assertEqual(
            new_picking.return_reason,
            "<p>Testing return reason</p>",
            "Return reason not correctly written",
        )

    def test_02_create_returns_without_reason(self):
        """New method to tes the return_reason is not written if not provided #T7254"""

        # Create and validate a stock.picking record #T7254
        picking = self.picking
        picking.button_validate()

        # Create a ReturnPicking wizard without providing return_reason #T7254
        return_wizard = self.env["stock.return.picking"].create(
            {
                "picking_id": picking.id,
            }
        )

        # Call the _create_returns method #T7254
        new_picking_id, picking_type_id = return_wizard._create_returns()

        # Get the return picking #T7254
        new_picking = self.env["stock.picking"].browse(new_picking_id)
        # Check that the return_reason is not set on the
        # new stock.picking record #T7254
        self.assertFalse(
            new_picking.return_reason, "Unexpected return reason set when none provided"
        )
