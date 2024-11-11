import requests
import json
from odoo import models, fields, api
import logging
import base64

from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    delivery_id = fields.Char(string="Delivery ID")
    subject = fields.Char(string="Subject", default="DIVERS")
    paymentType = fields.Char(string="Payment Type", default="ESPECES")
    caution = fields.Char(string="Caution", default="0")
    fragile = fields.Char(string="Fragile", default="0")
    rangeWeight = fields.Selection(selection=[
            ("ONE_FIVE", "Between 1Kg and 5Kg"),
            ("SIX_TEN", "Between 6Kg and 10Kg"),
            ("ELEVEN_TWENTY_NINE", "Between 11Kg and 29Kg"),
            ('MORE_30', 'More than 30Kg'),],string="Range Weight", default="ONE_FIVE")

    def call_shipping_api(self):
        for rec in self:
            # print(self.caution)
            # print(self.caution)
            # print(self.caution)
            # Retrieve cookies from system parameters
            if not rec.delivery_id:
                jsessionid = self.env['ir.config_parameter'].sudo().get_param('shipping_api.jsessionid')
                csrf_token = self.env['ir.config_parameter'].sudo().get_param('shipping_api.csrf_token')

                if not jsessionid or not csrf_token:
                    _logger.warning("Cookies are missing. Authentication might have failed.")
                    return

                url = "https://api.cathedis.delivery/ws/action"
                payload = json.dumps({
                    "action": "delivery.api.save",
                    "data": {
                        "context": {
                            "delivery": {
                                "recipient": rec.partner_id.name,
                                "city": rec.partner_id.city,
                                "sector": rec.partner_id.zip or "",
                                "phone": rec.partner_id.phone or rec.partner_id.mobile,
                                "amount": str(rec.sale_id.amount_total),
                                "caution": rec.caution,
                                "fragile": rec.fragile,
                                "declaredValue": str(rec.sale_id.amount_total),
                                "address": rec.partner_id.street or "",
                                "nomOrder": rec.name,
                                "comment": "Order from Odoo",
                                "rangeWeight": str(rec.rangeWeight),
                                "subject": rec.subject,
                                "paymentType": rec.paymentType,
                                "deliveryType": "Livraison CRBT",
                                "packageCount": "1",
                                "allowOpening": "0",
                                "tags": "API"
                            }
                        }
                    }
                })
                _logger.info(payload)
                headers = {
                    'Content-Type': 'application/json',
                    'Cookie': f'CSRF-TOKEN={csrf_token}; JSESSIONID={jsessionid}'
                }

                response = requests.post(url, headers=headers, data=payload)

                if response.status_code == 200:
                    response_data = response.json()
                    # Extract the delivery ID from the response data
                    delivery_id = response_data.get("data", [{}])[0].get("values", {}).get("delivery", {}).get("id")

                    if delivery_id:
                        rec.delivery_id = str(delivery_id)  # Store the delivery ID in the field
                        _logger.info("API call successful. Delivery ID: %s", delivery_id)
                    else:
                        _logger.warning("Delivery ID not found in the response.")
                        _logger.info("*****************************")
                        _logger.info(response_data)

                        raise ValueError("Delivery ID not found in the response.")
                else:
                    _logger.error("API call failed with status %s: %s", response.status_code, response.text)
                    raise ValueError("Delivery ID not found in the response.%s: %s", response.status_code, response.text)


    def action_generate_delivery_pdf(self):
        # self.ensure_one()
        ids = []
        for rec in self:
            ids.append(int(rec.delivery_id))
        jsessionid = self.env['ir.config_parameter'].sudo().get_param('shipping_api.jsessionid')
        csrf_token = self.env['ir.config_parameter'].sudo().get_param('shipping_api.csrf_token')
        if not jsessionid or not csrf_token:
            raise UserError(
                "Authentication cookies are missing. Please ensure the scheduled authentication is running correctly.")

        url = "https://api.cathedis.delivery/ws/action"
        payload = {
            "action": "delivery.print.bl4x4",
            "data": {
                "context": {
                    "_ids": ids,  # Ensure `delivery_id` is an integer
                    "_model": "com.tracker.delivery.db.Delivery"
                }
            }
        }
        headers = {
            'Content-Type': 'application/json',
            'Cookie': f'CSRF-TOKEN={csrf_token}; JSESSIONID={jsessionid}'
        }
        response = requests.post(url, json=payload, headers=headers)

        if response.status_code == 200:
            response_data = response.json()
            print(response.text)
            pdf_path = response_data.get("data", [{}])[0].get("view", {}).get("views", [{}])[0].get("name")
            if pdf_path:
                pdf_url = f"https://api.cathedis.delivery/{pdf_path}"
                return {
                    'type': 'ir.actions.act_url',
                    'url': pdf_url,
                    'target': 'new',
                }
            else:
                raise UserError("PDF URL not found in the response.")
        else:
            raise UserError(f"Failed to fetch PDF URL with status code: {response.status_code}")



    def action_refresh_pickup_request(self):
        ids = []
        for rec in self:
            ids.append(int(rec.delivery_id))

        # Retrieve cookies from system parameters
        jsessionid = self.env['ir.config_parameter'].sudo().get_param('shipping_api.jsessionid')
        csrf_token = self.env['ir.config_parameter'].sudo().get_param('shipping_api.csrf_token')

        if not jsessionid or not csrf_token:
            raise UserError("Authentication cookies are missing. Please ensure the scheduled authentication is running correctly.")

        # Set the required URL and headers
        url = "https://api.cathedis.delivery/ws/action"
        headers = {
            'Content-Type': 'application/json',
            'Cookie': f'CSRF-TOKEN={csrf_token}; JSESSIONID={jsessionid}'
        }

        # Define the payload with sample values; adjust as needed
        payload = json.dumps({
            "action": "action-refresh-pickup-request",
            "model": "com.tracker.pickup.db.PickupRequest",
            "data": {
                "context": {
                    "ids": ids,  # Adjust these values dynamically if needed
                    "pickupPointId": 26301      # Adjust this value as required
                }
            }
        })

        # Make the POST request
        response = requests.post(url, headers=headers, data=payload)

        # Check the response and handle errors
        if response.status_code == 200:
            response_data = response.json()
            if response_data.get("status") == 0:
                return response_data  # Successful response
            else:
                raise UserError(f"API Error: {response_data}")
        else:
            raise UserError(f"Failed to call API. Status Code: {response.status_code}, Response: {response.text}")