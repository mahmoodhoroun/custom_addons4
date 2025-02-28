# -*- coding: utf-8 -*-
###############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2024-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Anfas Faisal K (odoo@cybrosys.com)
#
#    This program is under the terms of the Odoo Proprietary License v1.0(OPL-1)
#    It is forbidden to publish, distribute, sublicense, or sell copies of the
#    Software or modified copies of the Software.
#
#    THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#    FITNESS FOR A PARTICULAR PURPOSE AND NON INFRINGEMENT. IN NO EVENT SHALL
#    THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,DAMAGES OR OTHER
#    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,ARISING
#    FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
#    DEALINGS IN THE SOFTWARE.
#
###############################################################################
import requests
import base64
from datetime import datetime
from woocommerce import API
from odoo import fields, models, _
from odoo.tests import common
from odoo.exceptions import UserError
from xmlrpc.client import ServerProxy, ProtocolError

category_ids = False
attribute_ids = False
api_res = False
auth_vals = False


class WooOperation(models.TransientModel):
    """Class for the model woo_operation.Contains fields and methods related to
       Woocommerce operations.
    """
    _name = 'woo.operation'
    _description = "Woo Operation"

    name = fields.Char(string="Instance Name", readonly=True,
                       help='Name of the instance.')
    consumer_key = fields.Char(string="Consumer Key", readonly=True,
                               help='Consumer Key of the instance')
    api_key = fields.Char(string="Api Key", readonly=True,
                          help='API Key of the instance')
    consumer_secret = fields.Char(string="Consumer Secret", readonly=True,
                                  help='Consumer Secret of the instance')
    store_url = fields.Char(string="Store URL", readonly=True,
                            help='Store URL of the instance')
    product_check = fields.Boolean(help='The import or export will only happen'
                                        ' if enabled.', string="Products", )
    customer_check = fields.Boolean(help='The import or export will only '
                                         'happen if enabled.',
                                    string="Customers")
    order_check = fields.Boolean(help='The import or export will only happen '
                                      'if enabled.', string="Orders")
    category_check = fields.Boolean(help='The import or export will only '
                                         'happen if enabled.',
                                    string="Categories")
    variants_check = fields.Boolean(help='The import or export will only '
                                         'happen if enabled.',
                                    string="Product Variants")
    currency = fields.Char(help='Currency of the Instance', string="Currency",
                           readonly=True, )
    start_date = fields.Date(help='If selected, will import the orders that '
                                  'created from this date.',
                             string="Start Date")
    end_date = fields.Date(help='If selected, will import the orders that '
                                'created till date.', string="End Date")
    sync_fun = fields.Boolean(help="Check sync state")
    company = fields.Boolean(help="if this field empty then created records"
                                  " available for all company",
                             string="Company")

    def get_api(self):
        """It returns the API object for operations.
            :return: Returns API object."""
        return API(
            url="" + self[-1].store_url + "/index.php/",  # Your store URL
            consumer_key=self[-1].consumer_key,  # Your consumer key
            consumer_secret=self[-1].consumer_secret,  # Your consumer secret
            wp_api=True,  # Enable the WP REST API integration
            version="wc/v3",  # WooCommerce WP REST API version
            timeout=500,
        )

    def get_auth(self):
        """Function to authenticate xml rpc endpoints and return the required
            values.
            :returns: Returns with dictionary of the merged key-value pairs."""
        # Connect to the Odoo server
        user_id = self.env.uid
        user = self.env['res.users'].sudo().browse(user_id)
        username = user.login
        password = self[-1].api_key
        db_name = common.get_db_name()
        url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')

        # Attempt to authenticate and handle redirects manually
        try:
            common_auth = ServerProxy('{}/xmlrpc/2/common'.format(url),
                                      allow_none=True, verbose=True)
            uid = common_auth.authenticate(db_name, username, password, {})
        except ProtocolError as e:
            if e.errcode == 307:
                # Handle the redirect manually
                redirect_url = e.headers.get('Location')
                if redirect_url:
                    common_auth = ServerProxy(redirect_url, allow_none=True,
                                              verbose=True)
                    uid = common_auth.authenticate(db_name, username, password,
                                                   {})
                else:
                    raise Exception(
                        "Error during authentication. No valid redirect URL found.")
            else:
                raise Exception(
                    "Error during authentication: {}".format(str(e)))

        data_model = ServerProxy('{}/xmlrpc/2/object'.format(url))
        return {'data_model': data_model, 'uid': uid, 'db_name': db_name,
                'password': password}

    def get_woo_import(self):
        """Method for importing data from woocommerce database."""
        if not (self.product_check or self.order_check or self.customer_check):
            raise UserError(_("Please enable at least one Method"))
        # Connect to the Odoo server
        global auth_vals
        auth_vals = self.get_auth()
        if self.order_check:
            self.order_data_import()
        else:
            if self.customer_check:
                self.customer_data_import()
            if self.product_check:
                self.product_data_import()

    def customer_data_import(self):
        """Function for getting all customers data through API."""
        app = self.get_api()
        page = 1  # The first page number to loop is page 1
        while True:
            customer_data = app.get('customers', params={
                'per_page': 100, 'page': page}).json()
            page += 1
            if not customer_data:
                break
            else:
                number_of_items = len(
                    list(filter(lambda x: isinstance(x, dict), customer_data)))
                model = self.env['ir.model'].search(
                    [('model', '=', "woo.operation")])
                self.env['job.cron'].sudo().create({
                    'model_id': model.id,
                    'function': "customer_create",
                    'data': customer_data,
                    'instance_id': self._context.get('active_id'),
                })
                self.env['woo.logs'].sudo().create({
                    'status': 'success',
                    'description': "Import - %s customers has been added to "
                                   "the queue." % number_of_items,
                    'trigger': 'queue'
                })

    def customer_create(self, customers, instance_id):
        """Function to create customers in Odoo.
            :param customers:Dictionary with customer values.
            :param instance_id:Record set of Woocommerce Instance."""
        customer_ids = self.env['res.partner'].search(
            [('type', '=', 'contact')])
        woo_ids = customer_ids.mapped('woo_id')
        cust_email = customer_ids.mapped('email')
        for rec in customers:
            if str(rec.get('id')) not in woo_ids and str(
                    rec.get('email')) in cust_email:
                # linking the already created contact in odoo to the
                # woocommerce contact without updating vals
                # since the email is unique in case of woocommerce
                existing_id = customer_ids.filtered(
                    lambda x: x.email == rec.get('email'))
                vals = {
                    'woo_id': rec.get('id'),
                    'woo_user_name': rec.get('username'),
                    'instance_id': instance_id.id if instance_id else False,
                    'company_id': self[-1].env.company.id if self[
                        -1].company else False,
                }
                existing_id.write(vals)
            else:
                # creating a new partner
                self.create_new_customer(rec, instance_id)

    def prepare_customer_vals(self, rec):
        """Method to return basic customer values that for the creation.
            :returns: The merged key-value pairs."""
        # Determine the name for the customer
        if rec.get("first_name") and not rec.get("last_name"):
            name = rec.get("first_name")
        elif rec.get("last_name") and not rec.get("first_name"):
            name = rec.get("first_name")
        elif rec.get("first_name") and rec.get("last_name"):
            # Combine first name and last name if both are available
            name_with = f'{rec.get("first_name")} {rec.get("last_name")}',
            name = str(name_with).strip("'(',)")
        elif not (rec.get("first_name") and rec.get("last_name")):
            # Use username if first name and last name are not available
            name = rec.get('username')

        # Check if a valid name is obtained
        if name:
            return {
                'company_type': "person",
                'name': name,
                'email': rec.get('email') if rec.get('email') else False,
                'woo_id': rec.get('id'),
                'woo_user_name': rec.get('username') if rec.get(
                    'username') else False,
                'company_id': self.env.company.id if self.env.company else False,
            }
        else:
            self.env['woo.logs'].sudo().create({
                'status': 'failed',
                'description': "Creation of customer with woo commerce id : %s"
                               " failed due to customer doesn't have a "
                               "name." % rec.get('id'),
                'trigger': 'import'
            })

    def has_at_least_one_value(self, dictionary):
        """Method to if the dictionary is empty or not.
            :param dictionary: Dictionary to check.
            :return: Returns False if dictionary is empty. Else return True."""
        for value in dictionary.values():
            if value:  # This checks if the value is non-empty.
                return True
            else:
                return False

    def create_new_customer(self, rec, instance_id):
        """Method to create new customer.
            :param rec: Dictionary of customer data.
            :param instance_id: Record set of woo_instance.
            :returns: The customer id."""
        # Prepare customer values
        val = self.prepare_customer_vals(rec)
        # Check if the email already exists
        mail_list = self.env['res.partner'].search(
            [('type', '=', 'contact')]).mapped('email')
        if val.get('email') in mail_list:
            self.env['woo.logs'].sudo().create({
                'status': 'failed',
                'trigger': 'import',
                'description': 'Customer with woo_id - %s creation failed. '
                               'Reason - Email already exists' % rec.get(
                    'id')})
        else:
            try:
                # Set the instance_id in customer values
                val['instance_id'] = instance_id.id if instance_id else False
                partner_id = self.env['res.partner'].create(val)

                # Create billing address if billing data is available
                if partner_id and self.has_at_least_one_value(rec['billing']):
                    if rec['billing'].get("first_name") and not rec[
                        'billing'].get("last_name"):
                        name = rec['billing'].get("first_name")
                    elif rec['billing'].get("last_name") and not rec[
                        'billing'].get("first_name"):
                        name = rec.get("first_name")
                    elif rec['billing'].get("first_name") and rec[
                        'billing'].get("last_name"):
                        dict = rec['billing']
                        name_with = f'{dict.get("first_name")} {dict.get("last_name")}',
                        name = str(name_with).strip("'(',)")
                    elif not (rec['billing'].get("first_name") and rec[
                        'billing'].get("last_name")):
                        name = ''
                    billing_address = {
                        'name': name if name else False,
                        'company_id': self.env.company.id if self.env.company else False,
                        'phone': rec['billing']['phone'] if rec['billing'][
                            'phone'] else False,
                        'street': rec['billing']['address_1'] if
                        rec['billing'][
                            'address_1'] else False,
                        'street2': rec['billing']['address_2'] if
                        rec['billing'][
                            'address_2'] else False,
                        'city': rec['billing']['city'] if rec['billing'][
                            'city'] else False,
                        'zip': rec['billing']['postcode'] if rec['billing'][
                            'postcode'] else False,
                        'state_id': self.env['res.country.state'].search(
                            [('code', '=', rec['billing']['state']),
                             ('country_id', '=',
                              rec['billing']['country'])]).id if
                        rec['billing']['country'] else False,
                        'country_id': self.env['res.country'].search(
                            [('code', '=', rec['billing']['country'])]).id if
                        rec['billing']['country'] else False,
                        'type': 'invoice',
                        'parent_id': partner_id.id,
                    }
                    self.env['res.partner'].sudo().create(billing_address)

                # Create delivery address if shipping data is available
                if partner_id and self.has_at_least_one_value(rec['shipping']):
                    if rec['shipping'].get("first_name") and not rec[
                        'shipping'].get("last_name"):
                        name = rec['shipping'].get("first_name")
                    elif rec['shipping'].get("last_name") and not rec[
                        'shipping'].get("first_name"):
                        name = rec.get("first_name")
                    elif rec['shipping'].get("first_name") and rec[
                        'shipping'].get("last_name"):
                        dict = rec['shipping']
                        name_with = f'{dict.get("first_name")} {dict.get("last_name")}',
                        name = str(name_with).strip("'(',)")
                    elif not (rec['shipping'].get("first_name") and rec[
                        'shipping'].get("last_name")):
                        name = ''
                    delivery_address = {
                        'name': name if name else False,
                        'company_id': self.env.company.id if self.env.company else False,
                        'phone': rec['shipping']['phone'] if rec['shipping'][
                            'phone'] else False,
                        'street': rec['shipping']['address_1'] if
                        rec['shipping'][
                            'address_1'] else False,
                        'street2': rec['shipping']['address_2'] if
                        rec['shipping'][
                            'address_2'] else False,
                        'city': rec['shipping']['city'] if rec['shipping'][
                            'city'] else False,
                        'zip': rec['shipping']['postcode'] if rec['shipping'][
                            'postcode'] else False,
                        'state_id': self.env['res.country.state'].search(
                            [('code', '=', rec['shipping']['state']), (
                                'country_id', '=',
                                rec['shipping']['country'])]).id if
                        rec['shipping']['country'] else False,
                        'country_id': self.env['res.country'].search(
                            [('code', '=', rec['shipping']['country'])]).id if
                        rec['shipping']['country'] else False,
                        'type': 'delivery',
                        'parent_id': partner_id.id,
                    }
                    self.env['res.partner'].sudo().create(delivery_address)

                # Log the success
                self.env['woo.logs'].sudo().create({
                    'status': 'success',
                    'trigger': 'import',
                    'description': "Customer ' %s ' with woo_id - %s created "
                                   "successfully" % (
                                       partner_id.name, partner_id.woo_id),
                })
                return partner_id
            except Exception as error:
                error_dict = error.__dict__
                self.env['woo.logs'].sudo().create({
                    'status': 'failed',
                    'trigger': 'import',
                    'description': 'Customer with woo_id - %s creation failed.'
                                   ' Reason - %s' % (rec.get('id'),
                                                     error_dict.get(
                                                         'faultString') if error_dict.get(
                                                         'faultString') else error),
                })

    def product_attribute_data_import(self):
        """Method for getting all products attributes data through API."""
        app = self.get_api()
        response = app.get("products/attributes", params={'per_page': 100})
        if response.status_code == 200:
            attributes = self.env['product.attribute'].search([])
            woo_ids = attributes.mapped('woo_id')
            for rec in response.json():
                if str(rec.get('id')) not in woo_ids:
                    # new attributes to be created!!
                    self.attribute_create(rec)
                else:
                    # need to check if there is a new value added for the
                    # given attribute and if yes: create
                    attribute = attributes.filtered(
                        lambda x: x.woo_id == str(rec.get('id')))
                    response = app.get(
                        "products/attributes/%s/terms" % int(
                            attribute.woo_id),
                        params={'per_page': 100})
                    if response.status_code == 200:
                        attribute_values = response.json()
                        if attribute_values:
                            filtered_data = [attr for attr in attribute_values
                                             if attr[
                                                 'name'] not in attribute.value_ids.mapped(
                                    'name')]
                            if filtered_data:
                                self.create_attribute_values(filtered_data,
                                                             attribute)

    def create_attribute_values(self, data, attribute_id):
        """Method to create product attribute values.
            :param data: Dictionary of product attribute values.
            :param attribute_id: Record set of product_attribute."""
        try:
            attr_vals = []
            attr_value_names = self.env['product.attribute.value'].search(
                []).mapped('name')
            for rec in data:
                if rec.get('name') not in attr_value_names:
                    val = {'woo_id': rec.get('id'), 'name': rec.get('name'),
                           'attribute_id': attribute_id.id}
                    attr_vals.append(val)
                else:
                    self.env['woo.logs'].sudo().create({
                        'status': 'failed',
                        'trigger': 'import',
                        'description': 'Product Attribute " %s " with '
                                       'woo_id - %s creation failed. Reason - '
                                       'Attribute value name exists. It should'
                                       ' be unique.' % (
                                           rec.get('name'), rec.get('id'),)})
            if attr_vals:
                self.env['product.attribute.value'].create(attr_vals)
        except Exception as error:
            error_dict = error.__dict__
            self.env['woo.logs'].sudo().create({
                'status': 'failed',
                'trigger': 'import',
                'description': 'Product Attribute " %s " with woo_id - %s '
                               'creation failed. Reason - %s' % (
                                   val.get('name'), val.get('woo_id'),
                                   error_dict.get(
                                       'faultString') if error_dict.get(
                                       'faultString') else error),
            })

    def attribute_create(self, attribute):
        """
        Method to create attributes.
        :param attribute: Dictionary of attribute values.
        """
        try:
            active_id = self._context.get('active_id')
            vals = {'display_type': 'radio',
                    'create_variant': 'always',
                    'name': attribute.get('name'),
                    'slug': attribute.get('slug'),
                    'woo_id': attribute.get('id'),
                    'instance_id': active_id if active_id else False}
            new_attribute_id = self.env['product.attribute'].create(vals)
            self.env['woo.logs'].sudo().create({
                'status': 'success',
                'trigger': 'import',
                'description': 'Attribute %s with woo_id %s created '
                               'successfully' % (
                                   new_attribute_id.name,
                                   new_attribute_id.woo_id),
            })
            if new_attribute_id:
                app = self.get_api()
                response = app.get(
                    "products/attributes/%s/terms" % attribute.get('id'),
                    params={'per_page': 100})
                if response.status_code == 200:
                    attribute_values = response.json()
                    if attribute_values:
                        self.create_attribute_values(attribute_values,
                                                     new_attribute_id)
        except Exception as error:
            error_dict = error.__dict__
            self.env['woo.logs'].sudo().create({
                'status': 'failed',
                'trigger': 'import',
                'description': 'Customer " %s " with woo_id - %s creation '
                               'failed. Reason - %s' % (
                                   attribute.get('name'), attribute.get('id'),
                                   error_dict.get(
                                       'faultString') if error_dict.get(
                                       'faultString') else error),
            })

    def product_data_import(self):
        """
        Method for getting all products data through API
        """
        global app
        app = self.get_api()
        page = 1  # The first page number to loop is page 1
        # creating new categories and attributes
        self.category_values()
        self.product_attribute_data_import()
        global api_res
        api_res = requests.get(
            'https://api.exchangerate-api.com/v4/latest/' + self.currency + '').json()
        while True:
            product_data = app.get('products', params={
                'per_page': 100, 'page': page}).json()
            page += 1
            if not product_data:
                break
            else:
                number_of_items = len(
                    list(filter(lambda x: isinstance(x, dict), product_data)))
                model = self.env['ir.model'].search(
                    [('model', '=', "woo.operation")])
                self.env['job.cron'].sudo().create({
                    'model_id': model.id,
                    'function': "product_create",
                    'data': product_data,
                    'instance_id': self._context.get('active_id'),
                })
                self.env['woo.logs'].sudo().create({
                    'status': 'success',
                    'description': 'Import - %s products has been added to '
                                   'the queue.' % number_of_items,
                    'trigger': 'queue'
                })

    def prepare_product_vals(self, data, instance_id):
        """
        Function to prepare product values to create a product.
        :param data: Dictionary of product data.
        :param instance_id: Record set of woo_instance.
        :returns: The merged key-value pairs.
        """
        category_id = 1
        # Get dimensions for the product
        dimensions_single = self.get_dimension(data.get('dimensions'))

        # Get linked product IDs for upsell and cross-sell
        upsell_ids = self.get_linked_product_ids(data.get('upsell_ids'),
                                                 instance_id) or []
        cross_sell_ids = self.get_linked_product_ids(
            data.get('cross_sell_ids'), instance_id) or []

        # Create tags and get their IDs
        tags = self.tags_create(data.get('tags'))
        tag_ids = [tag.id for tag in tags]

        # Prepare product values
        return {
            'name': data.get('name'),
            'detailed_type': 'product',
            'description': data.get('description'),
            'list_price': data.get('price'),
            'sale_ok': True if data.get('status') == 'publish' else False,
            'default_code': data.get('sku'),
            'purchase_ok': data.get('purchasable') or False,
            'weight': data.get('weight') or 0,
            'woo_id': data.get('id'),
            'company_id': self.env.company.id if self.env.company else False,
            'volume': dimensions_single,
            'external_url_product': data.get('permalink'),
            'categ_id': category_id,
            'optional_product_ids': upsell_ids,
            'alternative_product_ids': cross_sell_ids,
            'product_tag_ids': tag_ids or [],
        }

    def create_stock_vals(self, product, data):
        """ Method to create stock values for the given product.
            :param product:Record set of product_product.
            :param data: Dictionary of product data.
        """
        # Prepare stock values
        stock_vals = {
            'location_id': self.env.ref('stock.stock_location_stock').id,
            'inventory_quantity': data.get('stock_quantity'),
            'quantity': data.get('stock_quantity'),
            'product_id': product[0].id,
            'on_hand': True
        }
        # Create a stock record
        self.env['stock.quant'].create(stock_vals)

    def tags_create(self, data):
        """ Method to create product tags.
            :param data: Dictionary with tag data.
            :returns: The list of tag ids.
        """
        product_tag = []
        # Check if tag data is provided
        if data:
            # Iterate over each tag in the data
            for item in data:
                # Search for existing tags with the same name
                tag_ids = self.env['product.tag'].search(
                    [('name', '=', item['name'])])

                # If tags with the same name exist, add them to the product_tag list
                if tag_ids:
                    for tag_id in tag_ids:
                        if tag_id not in product_tag:
                            product_tag.append(tag_id)
                else:
                    # If tag with the same name doesn't exist, create a new tag
                    new_tag_id = self.env['product.tag'].create({
                        'name': item['name'],
                        'woo_id': item['id']
                    })

                    # Log the success of tag creation
                    self.env['woo.logs'].sudo().create({
                        'status': 'success',
                        'trigger': 'import',
                        'description': 'Product Tag %s with woo_id %s created '
                                       'successfully' % (
                                           new_tag_id.name, new_tag_id.woo_id),
                    })

                    # Add the newly created tag to the product_tag list
                    product_tag.append(new_tag_id)
        return product_tag

    def get_dimension(self, data):
        """
        Method to return dimension for a product.
        :param data: Dictionary of product data.
        :returns: The calculated dimension based on
                  length * width * height.
        """
        try:
            # Attempt to calculate the dimension based on length, width, and height
            dimensions_single = int(data['length']) * int(data['width']) * int(
                data['height'])
        except ValueError:
            # Handle the case where any of the dimensions is not a valid integer
            dimensions_single = 0
        return dimensions_single

    def get_attribute_line_vals(self, data):
        """
        Method to fetch and return attributes and its values.
        :param data: Data of product data.
        :returns: The merged key-value pairs.
        """
        # Fetch existing product attributes
        attr_ids = self.env['product.attribute'].sudo().search([])
        # Initialize dictionaries to store attribute values
        vals = {}
        dynamic_vals = {}

        # Iterate through each product data item
        for item in data:
            # Iterate through attributes of the item
            for attribute in item['attributes']:

                # Find attribute by woo_id
                attr_id = attr_ids.filtered(
                    lambda x: x.woo_id == str(attribute.get('id')))

                # If attribute exists, find corresponding attribute value
                if attr_id:
                    attr_val = attr_id.value_ids.filtered(
                        lambda x: x.name == attribute.get(
                            'options'))
                    # If attribute value exists, add it to the dictionary
                    if attr_val:
                        vals.setdefault(attr_id.id, []).append(attr_val.ids[0])
                else:
                    # If attribute doesn't have id , get name of the Attribute
                    if attribute.get('name'):

                        # Search Attribute by name
                        new_attribute = self.env['product.attribute'].search(
                            [('name', '=', attribute.get('name'))])

                        # Create a new attribute if not found
                        if not new_attribute:
                            new_attribute = self.env[
                                'product.attribute'].create(
                                {'name': attribute.get('name')})

                        # If attribute has options, create corresponding attribute values
                        if attribute.get('option'):
                            if not len(new_attribute) > 1:
                                new_value = new_attribute.value_ids.filtered(
                                    lambda x: x.name.lower() == attribute.get(
                                        'option').lower())

                                # Create a new attribute value if not found
                                if not new_value:
                                    new_value = self.env[
                                        'product.attribute.value'].create({
                                        'name': attribute.get('option'),
                                        'attribute_id': new_attribute.id,
                                    })

                                # Add the new value to the dynamic_vals dictionary
                                if new_value.id not in dynamic_vals.setdefault(
                                        new_attribute.id, []):
                                    dynamic_vals[new_attribute.id].append(
                                        new_value.id)
                            else:
                                # If multiple attributes found, filter based on options
                                new_attribute = new_attribute.filtered(
                                    lambda x: attribute.get(
                                        'option').lower() in x.value_ids.mapped(
                                        'name'))
                                if len(new_attribute) > 1:
                                    new_attribute = new_attribute[0]
                                new_value = new_attribute.value_ids.filtered(
                                    lambda x: x.name.lower() == attribute.get(
                                        'option').lower())

                                # Create a new attribute value if not found
                                if not new_value:
                                    new_value = self.env[
                                        'product.attribute.value'].create({
                                        'name': attribute.get('option'),
                                        'attribute_id': new_attribute.id,
                                    })

                                # Add the new value to the dynamic_vals dictionary
                                if new_value[
                                    0].id not in dynamic_vals.setdefault(
                                    new_attribute.id, []):
                                    dynamic_vals[new_attribute.id].append(
                                        new_value[0].id)

        # Prepare attribute line values using a list comprehension
        attribute_line_values = [(0, 0, {'attribute_id': attr_id,
                                         'value_ids': [(6, 0, value_ids)]})
                                 for attr_id, value_ids in vals.items()]

        # If dynamic_vals is not empty, add new lines to attribute_line_values
        if dynamic_vals:
            new_lines = [(0, 0, {'attribute_id': attr_id,
                                 'value_ids': [(6, 0, value_ids)]}) for
                         attr_id, value_ids in dynamic_vals.items()]
            attribute_line_values += new_lines
        return attribute_line_values

    def get_product_image(self, data):
        """
        Method to get the main product image and also the other images
        in product.
        :param data: Dictionary of product data.
        :returns: The dict of main image and other images if existed.
        """
        data_list = {}
        product_template_image_ids = []
        for index, value in enumerate(data.get('images')):
            if index == 0:
                data_list['main_image'] = {
                    'image_1920': base64.b64encode(
                        requests.get(data['images'][0]['src']).content)}
            else:
                product_template_image_ids.append((0, 0,
                                                   {'name': data.get('name'),
                                                    'image_1920': base64.b64encode(
                                                        requests.get(value[
                                                                         'src']).content)}))
        data_list['product_template_image_ids'] = product_template_image_ids
        return data_list

    def create_stock_variants(self, val, product):
        """
        Method to create stock for variants.
        :param val: Product data to create stock data.
        """
        for rec in val:
            variant_id = product.product_variant_ids.filtered(
                lambda x: x.woo_var_id == str(rec))
            if variant_id:
                stock_vals = {
                    'location_id': self.env.ref(
                        'stock.stock_location_stock').id,
                    'inventory_quantity': val.get(rec),
                    'quantity': val.get(rec),
                    'product_id': variant_id[0].id,
                    'on_hand': True
                }
                self.env['stock.quant'].sudo().create(stock_vals)

    def update_variant_stock_vals(self, val):
        """
        Method to return variant stock values.
        :param val: Product data to update stock values.
        :returns: The merged key-value pairs.
        """
        stock_vals = {}
        # Iterate over the records in the provided product data
        for rec in val:
            # Check if the product has stock management enabled and it is not a parent
            if rec.get('manage_stock') != 'parent' and rec.get('manage_stock'):
                # Check if the stock quantity is greater than 0
                if rec.get('stock_quantity') > 0:
                    # Add the variant ID and its stock quantity to the dictionary
                    stock_vals[rec.get('id')] = rec.get('stock_quantity')

        # Return the dictionary containing variant ID and stock quantity pairs
        return stock_vals

    def update_variants(self, val):
        """
        Method to return variant values.
        :param val: List of dictionary with product data.
        :returns: The merged key-value pairs.
        """
        # List to store the processed variant data
        variants_list = []
        # Odoo product attribute model
        attr_obj = self.env['product.attribute']
        for data in val:
            vals = {}  # Dictionary to store attribute-value mappings
            for attribute in data['attributes']:
                # If attribute has an 'id' field, search for the corresponding Odoo attribute
                if attribute.get('id'):
                    attr_id = attr_obj.search([]).filtered(
                        lambda x: x.woo_id == str(attribute.get('id')))
                    if attr_id:
                        # If Odoo attribute is found, find the corresponding attribute value
                        attr_val = attr_id.value_ids.filtered(
                            lambda x: x.name.lower() == attribute.get(
                                'option').lower())
                        if attr_val:
                            # Append the attribute value to the dictionary
                            vals.setdefault(attr_id.id, []).append(
                                attr_val.ids[0])
                elif attribute.get('name'):
                    # If attribute has a 'name' field, search for the corresponding Odoo attribute by name
                    attr_id = attr_obj.search(
                        [('name', '=', attribute.get('name'))])
                    if attr_id and len(attr_id) == 1:
                        # If exactly one Odoo attribute is found, find the corresponding attribute value
                        attr_val = attr_id.value_ids.filtered(
                            lambda x: x.name.lower() == attribute.get(
                                'option').lower())
                        if attr_val:
                            # Append the attribute value to the dictionary
                            vals.setdefault(attr_id.id, []).append(
                                attr_val.ids[0])
                    if attr_id and len(attr_id) > 1:
                        # If multiple Odoo attributes are found with the same name, narrow down to one
                        new_attribute = attr_id.filtered(
                            lambda x: attribute.get(
                                'option').lower() in x.value_ids.mapped(
                                'name'))
                        if len(new_attribute) > 1:
                            new_attribute = new_attribute[0]
                        # Find the corresponding attribute value for the narrowed down attribute
                        new_value = new_attribute.value_ids.filtered(
                            lambda x: x.name.lower() == attribute.get(
                                'option').lower())
                        if new_value:
                            # Append the attribute value to the dictionary
                            vals.setdefault(new_attribute.id, []).append(
                                new_value.ids[0])
            new_dict = {'image_variant_1920': base64.b64encode(
                requests.get(data['image']['src']).content) if data[
                'image'] else False,
                        'woo_var_id': data['id'],
                        'description': data['description'],
                        'default_code': data['sku'],
                        'weight': data['weight'],
                        'combination': vals if vals else False,
                        'volume': self.get_dimension(data['dimensions'])}
            variants_list.append(
                new_dict)  # Append the processed variant data to the list
        return variants_list

    def simple_product_create(self, data, instance_id):
        """
        Method to create a product without variants.
        :param data: Dictionary with product data
        :param instance_id: Record set of woo_instance.
        :returns: The id of created product.
        """
        # Prepare initial product values
        val_list = self.prepare_product_vals(data, instance_id)
        val_list['instance_id'] = instance_id.id if instance_id else False

        # Get image information
        image = self.get_product_image(data)

        # Set category information if available
        categories_value = data.get('categories')
        if categories_value:
            category_woo_id = categories_value[0].get('id')
            category_id = self.env['product.category'].search(
                [('woo_id', '=', category_woo_id)], limit=1)
            if category_id:
                val_list['categ_id'] = category_id.id

        # Update product template with image details
        if image.get('main_image'):
            val_list.update(image.get('main_image'))
        if image.get('product_template_image_ids'):
            val_list['product_template_image_ids'] = image.get(
                'product_template_image_ids')

        # Set product type to 'service' if it's virtual
        if data.get('virtual'):
            val_list['detailed_type'] = 'service'
        # grouped products
        if data.get('type') == 'grouped':
            val_list['detailed_type'] = 'consu'
            val_list['is_grouped_product'] = True
            grouped_product_ids = data.get('grouped_products', [])
            val_list['woo_product_values'] = grouped_product_ids
        # external products
        if data.get('type') == 'external':
            val_list['detailed_type'] = 'consu'
        val_list['woo_variant_check'] = True

        # Create the product template
        new_product_id = self.env['product.template'].create(val_list)

        # Log the creation status
        if new_product_id:
            self.env['woo.logs'].sudo().create({
                'status': 'success',
                'trigger': 'import',
                'description': 'Product %s with woo_id - %s created '
                               'successfully.' % (
                                   new_product_id.name, new_product_id.woo_id)
            })

            # Set product template category if available
            if new_product_id and categories_value:
                category_id = self.env['product.category'].search(
                    [('woo_id', '=', category_woo_id)], limit=1)
                if category_id:
                    new_product_id.categ_id = category_id.id

            # Create stock if manage_stock is enabled and stock_quantity is >= 1
            if data.get('stock_quantity') is not None:
                if new_product_id and data.get('manage_stock') and data.get(
                        'stock_quantity') >= 1:
                    # add stock for the product(variant)
                    variant = self.env['product.product'].search(
                        [('product_tmpl_id', '=', new_product_id.id)])
                    self.create_stock_vals(variant, data)
            return new_product_id.id

    def variant_product_tmpl_create(self, data, instance_id):
        """
        Method to create a product with variants.
        :param data:Dictionary of product data.
        :param instance_id: Record set of woo_instance.
        :returns: The id of created product template.
        """
        app = self.get_api()
        # Prepare initial product values
        val_list = self.prepare_product_vals(data, instance_id)
        val_list['instance_id'] = instance_id.id if instance_id else False

        # Get image information
        image = self.get_product_image(data)

        # Set category information
        categories_value = data.get('categories')
        if categories_value:
            category_woo_id = categories_value[0].get('id')
            category_id = self.env['product.category'].search(
                [('woo_id', '=', category_woo_id)], limit=1)
            if category_id:
                val_list['categ_id'] = category_id.id

        # Update product values with main image and additional images
        if image.get('main_image'):
            val_list.update(image.get('main_image'))
        if image.get('product_template_image_ids'):
            val_list['product_template_image_ids'] = image.get(
                'product_template_image_ids')
        try:
            # Fetch product variations from WooCommerce
            params = {"per_page": 100}
            response = app.get("products/%s/variations" % (data.get("id")),
                               params=params)
            variants = response.json()

        except Exception as error:
            message = ("Error While Importing Product Variants from "
                       "WooCommerce. \n%s") % error
            return message

        # Virtual Product
        if data.get('virtual'):
            val_list['detailed_type'] = 'service'
        variant_vals = {}
        # Initialize to avoid errors for products having no variant data.
        if variants:
            # Get attribute line values
            attribute_line_ids = self.get_attribute_line_vals(variants)
            if attribute_line_ids:
                val_list['attribute_line_ids'] = attribute_line_ids

            # Update variant values
            variant_vals = self.update_variants(variants)
            val_list['woo_variant_check'] = True

            # Update stock information for variants
            variant_stock_vals = self.update_variant_stock_vals(variants)

            # Create new product template
            new_product_id = self.env['product.template'].create(val_list)
            if new_product_id:
                # Log information about the created variant product
                self.env['woo.logs'].sudo().create({
                    'status': 'success',
                    'trigger': 'import',
                    'description': 'Variant Product " %s " with woo_id - %s created successfully' % (
                        new_product_id.name, new_product_id.woo_id),
                })

            product = self.env['product.template'].browse(new_product_id.id)
            if product:
                # Iterate through variant values
                for rec in variant_vals:
                    # Check if the variant has combinations
                    if rec['combination']:
                        attr_ids = [x for x in rec['combination'].keys()]
                        attr_value_ids = [x[0] for x in
                                          rec['combination'].values()]
                        # Search for product template attribute values
                        domain = [('product_tmpl_id', '=', product.id),
                                  ('attribute_id', 'in', attr_ids), (
                                      'product_attribute_value_id', 'in',
                                      attr_value_ids)]
                        product_templ_attr_value = self.env[
                            'product.template.attribute.value'].search(domain)
                        # Filter product variants based on attribute values
                        product_variant = product.product_variant_ids.filtered(
                            lambda
                                x: x.product_template_variant_value_ids.ids == product_templ_attr_value.ids)
                        # Check if the product variant exists
                        if product_variant:
                            # Remove the 'combination' key from variant values
                            del rec['combination']
                            # Update the product variant
                            product_variant[0].write(rec)

            # Create stock for variants
            if variant_stock_vals:
                self.create_stock_variants(variant_stock_vals, product)
        try:
            # Update the main image of the created product template
            if new_product_id and variant_vals[0]:
                new_product_id.write({
                    'image_variant_1920': variant_vals[0]['image_variant_1920']
                })

        except Exception as error:
            message = "Error while syncing Product Variants images from WooCommerce. \n%s" % (
                error)
            return message

    def product_create(self, products, instance_id):
        """
        Method to call functions that creates products.
        :param products: Dictionary of product data.
        :param instance_id: Record set of woo_instance.
        """
        product_ids = self.env['product.template'].search([])
        woo_ids = product_ids.mapped('woo_id')
        for rec in products:
            if str(rec.get('id')) not in woo_ids:
                if rec.get('type') in ['simple', 'variable', 'bundle',
                                       'grouped', 'external']:
                    # currently including these woocommerce product types only
                    if rec.get('type') in ['simple', 'bundle', 'grouped',
                                           'external']:
                        # no need to create variants for these products, so
                        # we can use a separate function
                        self.simple_product_create(rec, instance_id)
                    if rec.get('type') == 'variable':
                        # need to create variants for these products
                        self.variant_product_tmpl_create(rec, instance_id)

    def tax_data_import(self):
        """Method to import woo commerce taxes into Odoo."""
        try:
            active_id = self._context.get('active_id')
            app = self.get_api()
            res = app.get("taxes", params={"per_page": 100}).json()
            tax_ids = self.env['account.tax'].search([])
            woo_ids = tax_ids.mapped('woo_id')
            country_id = self.env.company.country_id.id
            tax_ids = []
            for recd in res:
                if str(recd.get('id')) not in woo_ids:
                    # If the WooCommerce tax ID is not in the existing Odoo tax IDs, create a new tax record
                    vals_tax = {
                        'name': recd.get('name'),
                        'amount': recd.get('rate'),
                        'woo_id': recd.get('id'),
                        'instance_id': active_id if active_id else False,
                        'tax_group_id': self.create_tax_group(recd),
                        'tax_class': recd.get('class'),
                        'description': recd.get('rate').split('.')[0] + ".00%",
                        'country_id': country_id if country_id else 1
                    }
                    tax_ids.append(vals_tax)
            if tax_ids:
                self.env['account.tax'].create(tax_ids)
            self.env['woo.logs'].sudo().create({
                'status': 'success',
                'description': 'Taxes imported successfully.',
                'trigger': 'import'
            })
        except Exception as error:
            error_dict = error.__dict__
            self.env['woo.logs'].sudo().create({
                'status': 'failed',
                'trigger': 'import',
                'description': 'Tax creation failed. Reason - %s' % (
                    error_dict.get('faultString') if error_dict.get(
                        'faultString') else error),
            })

    def create_tax_group(self, tax):
        """
        Method to create new tax group.
        :param tax: Dictionary of Woocommerce tax data.
        :return: Returns record set of account_tax_group.
        """
        active_id = self._context.get('active_id')
        country_id = self.env.company.country_id.id
        tax_group_id = self.env['account.tax.group'].search(
            [('woo_id', '=', tax.get("id"))]).id
        if not tax_group_id:
            # If no existing tax group is found, create a new tax group
            tax_group_id = self.env['account.tax.group'].create({
                'name': f'Woo {tax.get("name")}',
                'country_id': country_id if country_id else 1,
                'woo_id': tax.get("id"),
                'instance_id': active_id if active_id else False,
            }).id
        return tax_group_id

    def get_partner_from_order(self, data, partners, instance_id):
        """
        Method to fetch/create partner from order.
        :param data: Dictionary of Woocommerce order data.
        :param partners: Record set of res_partner.
        :param instance_id: Record set of woo_instance.
        :returns: The id of partner.
        """
        app = self.get_api()
        if data.get('customer_id'):
            # since the customer id is available it will have to be
            # already created initially.
            partner = partners.filtered(
                lambda x: x.woo_id == str(data.get('customer_id')))
            if partner:
                return partner.id
            else:
                customer_data = app.get(
                    'customers/%s' % data.get('customer_id'), params={
                        'per_page': 100, 'page': 1}).json()
                if customer_data:
                    # creating a new partner
                    partner_id = self.create_new_customer(customer_data,
                                                          instance_id)
                    if partner_id:
                        self.env['woo.logs'].sudo().create({
                            'status': 'success',
                            'trigger': 'import',
                            'description': 'Customer for the order with '
                                           'id - %s created '
                                           'successfully.' % data.get('id'),
                        })
                        return partner_id
        else:
            address_data = {}
            if self.has_at_least_one_value(data['billing']):
                address_data = data['billing']
            elif self.has_at_least_one_value(data['shipping']):
                address_data = data['shipping']
            if address_data:
                if address_data.get("first_name") and not address_data.get(
                        "last_name"):
                    name = address_data.get("first_name")
                elif address_data.get("last_name") and not address_data.get(
                        "first_name"):
                    name = address_data.get("first_name")
                elif address_data.get("first_name") and address_data.get(
                        "last_name"):
                    name_with = f'{address_data.get("first_name")} {address_data.get("last_name")}',
                    name = str(name_with).strip("'(',)")
                elif not (address_data.get("first_name") and address_data.get(
                        "last_name")):
                    name = None
                # to create a new customer
                if name:
                    if data.get('email') and str(
                            data.get('email')) in partners.mapped('email'):
                        # in this case when a random mail id given is matching
                        # the already existing partner mail.
                        self.env['woo.logs'].sudo().create({
                            'status': 'success',
                            'trigger': 'import',
                            'description': 'Customer assignation has been '
                                           'failed for the order with '
                                           'woo_id - %s. Email id already '
                                           'assigned for another '
                                           'partner.' % data.get('id'),
                        })
                        return False
                    else:
                        partner_data = self.prepare_customer_vals(
                            data['billing'])
                        if partner_data:
                            partner_data[
                                'instance_id'] = instance_id.id if instance_id else False
                            partner_id = self.env['res.partner'].create(
                                partner_data)
                            if partner_id:
                                self.env['woo.logs'].sudo().create({
                                    'status': 'success',
                                    'trigger': 'import',
                                    'description': 'Customer for the order '
                                                   'with id - %s created '
                                                   'successfully.'
                                                   '' % data.get('id'),
                                })
                                return partner_id
                else:
                    partner = self.env.ref(
                        'woo_commerce.woocommerce_guest').id
                    self.env['woo.logs'].sudo().create({
                        'status': 'success',
                        'trigger': 'import',
                        'description': 'Default customer has been assigned for'
                                       ' the order with woo_id - %s since '
                                       'customer name is not provided in the '
                                       'data.' % data.get('id'),
                    })
                    return partner

    def create_order(self, orders, instance_id):
        """
        Method to create Woocommerce order in odoo.
        :param orders: Dictionary of Woocommerce order data.
        :param instance_id: Record set of woo_instance.
        """
        try:
            order_ids = self.env['sale.order'].search([
                ('woo_id', '!=', False)
            ])
            app = self.get_api()
            woo_ids = order_ids.mapped('woo_id')
            # Loop through each order in the imported data
            for item in orders:

                if str(item.get('id')) not in woo_ids:
                    partner_ids = self.env['res.partner'].search(
                        [('type', '=', 'contact')])
                    partner_id = self.get_partner_from_order(item, partner_ids,
                                                             instance_id)
                    if partner_id:
                        order_create_date = \
                        item.get('date_created').split('T')[
                            0]
                        date_time_obj = datetime.strptime(order_create_date,
                                                          '%Y-%m-%d').date()
                    if partner_id is None:
                        # If no partner found, use the guest partner
                        guest_partner = self.env.ref(
                            'woo_commerce.woocommerce_guest')
                        partner_id = guest_partner.id if guest_partner else False
                        # Extract order creation date from the response
                        order_create_date = \
                        item.get('date_created').split('T')[
                            0]
                        date_time_obj = datetime.strptime(order_create_date,
                                                          '%Y-%m-%d').date()
                    state = 'draft'
                    woo_state = 'draft'
                    # Map Woocommerce order status to Odoo sale order states
                    if item.get('status') == 'pending':
                        state = 'sale'
                        woo_state = 'pending_payment'
                    elif item.get('status') == 'processing':
                        state = 'sale'
                        woo_state = 'processing'
                    elif item.get('status') == 'on-hold':
                        state = 'sale'
                        woo_state = 'on_hold'
                    elif item.get('status') == 'completed':
                        state = 'sale'
                        woo_state = 'completed'
                    elif item.get('status') == 'cancelled':
                        state = 'cancel'
                        woo_state = 'cancelled'
                    elif item.get('status') == 'refunded':
                        state = 'sale'
                        woo_state = 'refunded'
                    elif item.get('status') == 'failed':
                        state = 'sent'
                        woo_state = 'failed'
                    elif item.get('status') == 'draft':
                        state = 'draft'
                        woo_state = 'draft'
                    # Prepare values for creating the sale order
                    val_list = {
                        'partner_id': partner_id if type(
                            partner_id) is int else partner_id.id,
                        'date_order': date_time_obj,
                        'woo_id': item.get('id'),
                        'instance_id': instance_id.id if instance_id else False,
                        'woo_order_key': item.get('order_key'),
                        'state': state,
                        'woo_order_status': woo_state,
                    }
                    orderline = []
                    # Process line items from the response
                    for line_item in item.get('line_items'):
                        woo_tax = []
                        for tax in line_item['taxes']:
                            woo_tax.append(str(tax['id']))
                        # Search for tax IDs in Odoo based on WooCommerce tax IDs
                        tax_id = self.env['account.tax'].search([]).filtered(
                            lambda r: r.woo_id in woo_tax)

                        main_product = self.env['product.template'].search(
                            []).filtered(
                            lambda r: r.woo_id == str(line_item['product_id']))

                        if main_product:
                            main_product = main_product[0]
                            if len(main_product.product_variant_ids) > 1:
                                product = self.env['product.product'].search(
                                    []).filtered(
                                    lambda r: r.woo_var_id == str(
                                        line_item['variation_id']))
                                if product:
                                    product = product[0]
                            else:
                                product = main_product.product_variant_ids[0]
                            if product:
                                if item.get('status') == 'refunded':
                                    # For refunded products, set the price to 0
                                    val = {
                                        'name': product.name,
                                        'product_id': product.id,
                                        'price_unit': 0.0,
                                        # Set price to 0 for refunded products
                                        'product_uom_qty': line_item[
                                            'quantity'],
                                        'tax_id': tax_id.ids,
                                        'customer_lead': 1,
                                    }
                                    orderline.append((0, 0, val))
                                elif item.get('coupon_lines'):
                                    # For products with coupon lines, set the price discounts
                                    val = {
                                        'name': product.name,
                                        'product_id': product.id,
                                        'product_uom_qty': line_item[
                                            'quantity'],
                                        'price_unit': float(
                                            line_item['price']),
                                        'tax_id': tax_id.ids,
                                        'customer_lead': 1,
                                    }
                                    orderline.append((0, 0, val))
                                else:
                                    # For other products, set the price from the line item
                                    val = {
                                        'name': product.name,
                                        'product_id': product.id,
                                        'price_unit': line_item['price'],
                                        'product_uom_qty': line_item[
                                            'quantity'],
                                        'tax_id': tax_id.ids,
                                        'customer_lead': 1,
                                    }
                                    orderline.append((0, 0, val))
                        else:
                            # Create a new product if the main product doesn't exist
                            products_data = app.get(
                                'products/%s' % line_item['product_id'],
                                params={
                                    'per_page': 100, 'page': 1}).json()
                            if products_data.get('type') in ['simple',
                                                             'variable',
                                                             'bundle',
                                                             'grouped',
                                                             'external']:
                                # currently including these woocommerce
                                # product types only
                                product = False
                                if products_data.get('type') in ['simple',
                                                                 'bundle']:
                                    # No need to create variants for these products
                                    # Use a separate function for these product types
                                    simple_product = self.simple_product_create(
                                        products_data, instance_id)
                                    if simple_product:
                                        if type(simple_product) == int:
                                            product = self.env[
                                                'product.template'].browse(
                                                simple_product)
                                        else:
                                            product = simple_product
                                        if product:
                                            product = \
                                                product[0].product_variant_ids[
                                                    0]
                                if products_data.get('type') == 'variable':
                                    # need to create variants for these
                                    # products
                                    self.variant_product_tmpl_create(
                                        products_data, instance_id)
                                    product = self.env[
                                        'product.product'].filtered(
                                        lambda r: r.woo_var_id == str(
                                            line_item['id']))
                                if product:
                                    val = {
                                        'name': product.name,
                                        'product_id': product.id,
                                        'product_uom_qty': line_item[
                                            'quantity'],
                                        'price_unit': line_item['price'],
                                        'tax_id': tax_id.ids,
                                        'customer_lead': 1
                                    }
                                    orderline.append((0, 0, val))
                    # Process shipping lines from the response
                    for line_item in item.get('shipping_lines'):
                        if not line_item.get('method_id') or line_item.get(
                                'method_id') == 'other':
                            product = self.env.ref(
                                'woo_commerce.product_product_woocommerce_other')
                        elif line_item.get('method_id') == 'flat_rate':
                            product = self.env.ref(
                                'woo_commerce.product_product_flat_delivery')
                        elif line_item.get('method_id') == 'local_pickup':
                            product = self.env.ref(
                                'woo_commerce.product_product_local_pickup')
                        elif line_item.get('method_id') == 'pickup_location':
                            product = self.env.ref(
                                'woo_commerce.product_product_local_pickup')
                        elif line_item.get('method_id') == 'local_rate':
                            product = self.env.ref(
                                'woo_commerce.product_product_local_delivery')
                        elif line_item.get('method_id') == 'free_shipping':
                            product = self.env.ref(
                                'woo_commerce.product_product_woocommerce_free_delivery')

                        val = {
                            'name': product.name,
                            'product_id': product.product_variant_ids[0].id,
                            'tax_id': False,
                            'price_unit': float(line_item['total']),
                            'product_uom_qty': 1,
                            'customer_lead': 1,
                        }
                        orderline.append((0, 0, val))

                    # Process fee lines from the response
                    if item.get('fee_lines'):
                        for line_item in item.get('fee_lines'):
                            product = self.env.ref(
                                'woo_commerce.woocommerce_fee_lines')
                            val = {
                                'name': product.name,
                                'product_id': product.product_variant_ids[
                                    0].id,
                                'tax_id': False,
                                'price_unit': float(line_item['total']),
                                'product_uom_qty': 1,
                                'customer_lead': 1,
                            }
                            orderline.append((0, 0, val))

                    # Process coupon lines from the response
                    if item.get('coupon_lines'):
                        for line_item in item.get('coupon_lines'):
                            if line_item.get('discount', None):
                                product = self.env.ref(
                                    'woo_commerce.woocommerce_coupons')
                                val = {
                                    'name': product.name,
                                    'product_id': product.product_variant_ids[
                                        0].id,
                                    'tax_id': False,
                                    'price_unit': -1 * float(
                                        line_item['discount']),
                                    'product_uom_qty': 0,
                                    'customer_lead': 1,
                                }
                                orderline.append((0, 0, val))
                    if orderline:
                        val_list['order_line'] = orderline
                    # Create the sale order in Odoo
                    sale_order = self.env['sale.order'].sudo().create(val_list)
                    # Log success for imported order
                    self.env['woo.logs'].sudo().create({
                        'status': 'success',
                        'description': 'Orders %s with woo_id %s imported '
                                       'successfully.' % (
                                           sale_order.name,
                                           str(item.get('id'))),
                        'trigger': 'import'
                    })
        except Exception as e:
            # Log exception error
            self.env['woo.logs'].sudo().create({
                'status': 'failed',
                'description': f"Failed to import Woocommerce orders. Error: {str(e)}",
                'trigger': 'import'
            })

    def order_data_import(self):
        """
        Method to import woo commerce orders, its also import all products,
        customers.
        """
        global app
        app = self.get_api()
        global api_res
        api_res = requests.get(
            'https://api.exchangerate-api.com/v4/latest/' + self.currency + '').json()
        # creating new categories and attributes
        self.category_values()
        self.product_attribute_data_import()
        self.tax_data_import()
        page = 1  # The first page number to loop is page 1
        orders = []
        while True:
            order_data = app.get('orders', params={
                'per_page': 100, 'page': page}).json()
            page += 1
            if not order_data:
                break
            orders += order_data
        chunk_size = 50
        context = []
        chunk = []
        if self.start_date and self.end_date:
            for rec in orders:
                order_create_date = rec.get('date_created').split('T')[0]
                ord_date = datetime.strptime(order_create_date,
                                             '%Y-%m-%d').date()
                if self.start_date <= ord_date <= self.end_date:
                    chunk.append(rec)
                    if len(chunk) == chunk_size:
                        context.append(chunk)
                        chunk = []
        elif self.start_date and not self.end_date:
            for rec in orders:
                order_create_date = rec.get('date_created').split('T')[0]
                ord_date = datetime.strptime(order_create_date,
                                             '%Y-%m-%d').date()
                if ord_date >= self.start_date:
                    chunk.append(rec)
                    if len(chunk) == chunk_size:
                        context.append(chunk)
                        chunk = []
        elif self.end_date and not self.start_date:
            for rec in orders:
                order_create_date = rec.get('date_created').split('T')[0]
                ord_date = datetime.strptime(order_create_date,
                                             '%Y-%m-%d').date()
                if ord_date <= self.end_date:
                    chunk.append(rec)
                    if len(chunk) == chunk_size:
                        context.append(chunk)
                        chunk = []
        else:
            for i in range(0, len(orders), chunk_size):
                context.append(orders[i:i + chunk_size])
        if context:
            for rec in context:
                number_of_items = len(
                    list(filter(lambda x: isinstance(x, dict), rec)))
                model = self.env['ir.model'].search(
                    [('model', '=', "woo.operation")])
                self.env['job.cron'].sudo().create({
                    'model_id': model.id,
                    'function': "create_order",
                    'data': rec,
                    'instance_id': self._context.get('active_id'),
                })
                self.env['woo.logs'].sudo().create({
                    'status': 'success',
                    'description': 'Import - %s orders has been added to the '
                                   'queue.' % number_of_items,
                    'trigger': 'queue'
                })

    def create_or_get_category(self, category_data, categories):
        """
        Method to fetch/create category.
        :param category_data: Dictionary of Woocommerce category data.
        :param categories: Record set of product_category
        :returns: The object of category.
        """
        # Check if the category_data exists in Odoo
        try:
            category = self.env['product.category'].search([]).filtered(
                lambda r: r.woo_id == str(category_data.get('id')))
            if not category:
                # The category does not exist, so create it
                active_id = self._context.get('active_id')
                category_name = category_data['name']
                parent_id = category_data['parent']
                woo_id = category_data['id']
                # If the category has a parent, create it recursively
                parent_category_id = None
                if category_name == 'Uncategorized':
                    return None
                if parent_id:
                    parent_category = next(
                        (c for c in categories if c["id"] == parent_id), None)
                    if parent_category:
                        parent_category_id = self.create_or_get_category(
                            parent_category, categories)
                # Create the current category
                vals = {
                    'name': category_name,
                    'parent_id': parent_category_id.id if parent_category_id else False,
                    'woo_id': woo_id,
                    'instance_id': active_id if active_id else False
                }
                category = self.env['product.category'].create(vals)
                self.env['woo.logs'].sudo().create({
                    'status': 'success',
                    'trigger': 'import',
                    'description': 'Product Category %s with woo_id - %s '
                                   'created successfully.' % (
                                       category.name, category.woo_id)})
            return category
        except Exception as error:
            error_dict = error.__dict__
            self.env['woo.logs'].sudo().create({
                'status': 'failed',
                'trigger': 'import',
                'description': 'Product Category " %s " with woo_id - %s '
                               'creation failed. Reason - %s' % (
                                   category_data.get('name'),
                                   category_data.get('woo_id'),
                                   error_dict.get(
                                       'faultString') if error_dict.get(
                                       'faultString') else error),
            })

    def category_values(self):
        """
        Method to set category values to product.
        """
        page = 1  # The first page number to loop is page 1
        categories = []
        while True:
            category_data = app.get('products/categories',
                                    params={'per_page': 100,
                                            'page': page}).json()
            page += 1
            if not category_data:
                break
            categories += category_data
        if categories:
            woo_ids = self.env['product.category'].search([]).mapped('woo_id')
            for category_data in categories:
                if str(category_data.get('id')) not in woo_ids:
                    self.create_or_get_category(category_data, categories)

    def get_linked_product_ids(self, upsell_ids, instance_id):
        """
        Method to set upsell, cross-sell products.
        :param upsell_ids: Record set of products.
        :param instance_id: Record set of woo_instance.
        :return: Returns list with product ids.
        """
        product_ids = self.env['product.template'].search([])
        product_var_ids = self.env['product.product'].search([])
        val_list = []
        if upsell_ids:
            woo_ids = product_ids.mapped('woo_id')
            woo_var_ids = product_var_ids.mapped('woo_var_id')
            for item in upsell_ids:
                if str(item) in woo_ids:
                    # first checking the id in product templates
                    product_id = product_ids.filtered(
                        lambda r: r.woo_id == str(item))
                    if product_id:
                        val_list.append(product_id[0].id)
                elif str(item) in woo_var_ids:
                    # checking if the optional product added is a variant in
                    # odoo and if yes then adding its template
                    product_id = product_var_ids.filtered(
                        lambda r: r.woo_var_id == str(item))
                    if product_id:
                        val_list.append(product_id[0].product_tmpl_id.id)
        return val_list

    def create_attributes(self):
        """
        Method for getting all attributes data through API, it will
        create attributes in odoo.
        """
        global attribute_ids
        attribute_ids = self.env['product.attribute'].search([])
        woo_ids = attribute_ids.mapped('woo_id')
        app = self.get_api()
        attributes = app.get("products/attributes",
                             params={"per_page": 100}).json()
        for attr in attributes:
            if str(attr['id']) not in woo_ids:
                self.env['product.attribute'].sudo().create({
                    'name': attr['name'],
                    'display_type': 'radio',
                    'create_variant': 'no_variant',
                    'woo_id': attr['id'],
                    'instance_id': self._context.get('active_id').id
                })
                woo_ids.append(str(attr['id']))
        attribute_ids = self.env['product.attribute'].search([])

    def attribute_values(self, attributes):
        """
        Method for update the attribute values.
        :param attributes: Dictionary of Woocommerce product attributes.
        """
        global attribute_ids
        attribute_ids = self.env['product.attribute']
        for attr in attributes:
            attribute_id = attribute_ids.search([
                ('woo_id', '=', attr.get('id'))
            ])
            if attribute_id:
                values = attribute_id[0].value_ids.mapped('name')
                for item in attr['options']:
                    if item not in values:
                        attribute_id.write({
                            'value_ids': [
                                fields.Command.create({
                                    'name': item
                                })
                            ]
                        })

    def calc_currency_rate(self, price, action):
        """
        Method to convert currency.
        :param price: Price to convert.
        :param action: Integer value.
        :return: Returns True or False.
        """
        currency = self.env.company.currency_id.name
        global api_res
        if api_res:
            currency_rate = api_res['rates']
            if action == 1:
                value = round(float(price) * currency_rate[currency], 4
                              ) if price else 0
            else:
                value = round(float(price) / currency_rate[currency], 4
                              ) if price else 0
            return value
        else:
            return False

    def sync_details(self):
        """
        Method for sync data, it creates products, customers, orders also
        updated field in odoo based on Woocommerce.
        """
        global auth_vals
        auth_vals = self.get_auth()
        self.customer_data_sync()
        self.product_data_sync()
        self.order_data_sync()

    def write_order_data(self, data, instance_id):
        """
        Method for syncing order datas, it creates/write products,
        customers, orders also updated field in odoo based on Woocommerce.
        :param data: Dictionary of order data.
        :param instance_id:Record set of woo_instance.
        """
        order_ids = self.env['sale.order'].search([
            ('woo_id', '!=', False)
        ])
        for item in data:
            partner_id = False
            sale_order = order_ids.filtered(
                lambda r: r.woo_id == str(item['id']))
            if sale_order:
                exist_partner = self.env['res.partner'].search(
                    [('woo_id', '!=', False), (
                        'type', '=', 'contact')]).filtered(
                    lambda x: x.woo_id == str(item.get('customer_id')))
                if exist_partner:
                    partner_id = exist_partner
                else:
                    if item.get('customer_id') == 0:
                        partner_id = self.env.ref(
                            'woo_commerce.woocommerce_guest')
                    else:
                        customer_data = app.get(
                            'customers/%s' % item.get('customer_id'), params={
                                'per_page': 100, 'page': 1}).json()
                        if customer_data:
                            # creating a new partner
                            partner_id = self.create_new_customer(
                                customer_data, instance_id)

                # Extract order creation date from the response
                order_create_date = item.get('date_created').split('T')[
                    0]
                date_time_obj = datetime.strptime(order_create_date,
                                                  '%Y-%m-%d').date()
                # Initialize state values for the sale order
                # To Remove the order lines and Update it again
                sale_order.sudo().write({'state': 'draft'})
                # Map WooCommerce order status to Odoo sale order states
                if item.get('status') == 'pending':
                    state = 'sale'
                    woo_state = 'pending_payment'
                elif item.get('status') == 'processing':
                    state = 'sale'
                    woo_state = 'processing'
                elif item.get('status') == 'on-hold':
                    state = 'sale'
                    woo_state = 'on_hold'
                elif item.get('status') == 'completed':
                    state = 'sale'
                    woo_state = 'completed'
                elif item.get('status') == 'cancelled':
                    state = 'cancel'
                    woo_state = 'cancelled'
                elif item.get('status') == 'refunded':
                    state = 'sale'
                    woo_state = 'refunded'
                elif item.get('status') == 'failed':
                    state = 'cancel'
                    woo_state = 'failed'
                elif item.get('status') == 'draft':
                    state = 'draft'
                    woo_state = 'draft'
                # Prepare the values for creating the sale order
                val_list = {
                    'partner_id': partner_id,
                    'date_order': date_time_obj,
                    'woo_id': item.get('id'),
                    'instance_id': instance_id.id if instance_id else False,
                    'woo_order_key': item.get('order_key'),
                    'state': state,
                    'woo_order_status': woo_state,
                    'company_id': instance_id.company_id.id if instance_id else False,
                    'currency_id': instance_id.currency if instance_id else False
                }

                orderline = []  # List to store order lines
                # Process line items from the response
                for line_item in item.get('line_items'):
                    woo_tax = []
                    for tax in line_item['taxes']:
                        woo_tax.append(str(tax['id']))

                    # Search for tax IDs in Odoo based on WooCommerce tax IDs
                    tax_id = self.env['account.tax'].sudo().search(
                        []).filtered(lambda r: r.woo_id in woo_tax)

                    main_product = self.env[
                        'product.template'].sudo().search([]).filtered(
                        lambda r: r.woo_id == str(
                            line_item['product_id']))
                    if main_product:
                        main_product = main_product[0]

                        # Check if there are multiple variants for the main product
                        if len(main_product.product_variant_ids) > 1:
                            #If more than one the get variant ID
                            product = self.env[
                                'product.product'].sudo().search(
                                []).filtered(
                                lambda r: r.woo_var_id == str(
                                    line_item['variation_id']))

                            if product:
                                product = product[0]

                        else:
                            # Use the main product if there is only one variant
                            product = main_product.product_variant_ids[0]
                        if product:
                            if item.get('status') == 'refunded':
                                # For refunded products, set the price to 0
                                val = {
                                    'name': product.name,
                                    'product_id': product.id,
                                    'price_unit': 0.0,
                                    # Set price to 0 for refunded products
                                    'product_uom_qty': line_item[
                                        'quantity'],
                                    'tax_id': tax_id.ids,
                                    'customer_lead': 1,
                                }
                                orderline.append((0, 0, val))
                            elif item.get('coupon_lines'):
                                # For products with coupon lines, set the price discounts
                                val = {
                                    'name': product.name,
                                    'product_id': product.id,
                                    'product_uom_qty': line_item[
                                        'quantity'],
                                    'price_unit': float(
                                        line_item['price']),
                                    'tax_id': tax_id.ids,
                                    'customer_lead': 1,
                                }
                                orderline.append((0, 0, val))
                            else:
                                # For other products, set the price from the line item
                                val = {
                                    'name': product.name,
                                    'product_id': product.id,
                                    'price_unit': line_item['price'],
                                    'product_uom_qty': line_item[
                                        'quantity'],
                                    'tax_id': tax_id.ids,
                                    'customer_lead': 1,
                                }
                                orderline.append((0, 0, val))

                    else:
                        # Create a new product if the main product doesn't exist
                        products_data = app.get(
                            'products/%s' % line_item['product_id'],
                            params={
                                'per_page': 100, 'page': 1}).json()
                        if products_data.get('type') in ['simple',
                                                         'variable',
                                                         'bundle',
                                                         'grouped',
                                                         'external']:
                            # currently including these woocommerce
                            # product types only
                            product = False
                            if products_data.get('type') in ['simple',
                                                             'bundle',
                                                             'external',
                                                             'grouped']:
                                simple_product = self.simple_product_create(
                                    products_data, instance_id)
                                if simple_product:
                                    if type(simple_product) == int:
                                        product = self.env[
                                            'product.template'].sudo().browse(
                                            simple_product)
                                    else:
                                        product = simple_product
                                    if product:
                                        product = \
                                        product[0].product_variant_ids[0]
                            if products_data.get('type') == 'variable':
                                # Create product variants for variable products
                                self.variant_product_tmpl_create(
                                    products_data, instance_id)
                                product = self.env[
                                    'product.product'].filtered(
                                    lambda r: r.woo_var_id == str(
                                        line_item['id']))
                                if product:
                                    val = {
                                        'name': product.name,
                                        'product_id': product.id,
                                        'product_uom_qty': line_item[
                                            'quantity'],
                                        'price_unit': line_item['price'],
                                        'tax_id': tax_id.ids,
                                        'customer_lead': 1
                                    }
                                    orderline.append((0, 0, val))
                # Process shipping lines from the response
                for line_item in item.get('shipping_lines'):
                    if not line_item.get('method_id') or line_item.get(
                            'method_id') == 'other':
                        product = self.env.ref(
                            'woo_commerce.product_product_woocommerce_other')
                    elif line_item.get('method_id') == 'flat_rate':
                        product = self.env.ref(
                            'woo_commerce.product_product_flat_delivery')
                    elif line_item.get('method_id') == 'local_pickup':
                        product = self.env.ref(
                            'woo_commerce.product_product_local_pickup')
                    elif line_item.get('method_id') == 'pickup_location':
                        product = self.env.ref(
                            'woo_commerce.product_product_local_pickup')
                    elif line_item.get('method_id') == 'local_rate':
                        product = self.env.ref(
                            'woo_commerce.product_product_local_delivery')
                    elif line_item.get('method_id') == 'free_shipping':
                        product = self.env.ref(
                            'woo_commerce.product_product_woocommerce_free_delivery')
                    val = {
                        'name': product.name,
                        'product_id': product.product_variant_ids[0].id,
                        'tax_id': False,
                        'price_unit': float(line_item['total']),
                        'product_uom_qty': 1,
                        'customer_lead': 1,
                    }
                    orderline.append((0, 0, val))
                # Process fee lines from the response
                if item.get('fee_lines'):
                    for line_item in item.get('fee_lines'):
                        product = self.env.ref(
                            'woo_commerce.woocommerce_fee_lines')
                        val = {
                            'name': product.name,
                            'product_id': product.product_variant_ids[
                                0].id,
                            'tax_id': False,
                            'price_unit': float(line_item['total']),
                            'product_uom_qty': 1,
                            'customer_lead': 1,
                        }
                        orderline.append((0, 0, val))
                if item.get('coupon_lines'):
                    for line_item in item.get('coupon_lines'):
                        if line_item.get('discount', None):
                            product = self.env.ref(
                                'woo_commerce.woocommerce_coupons')
                            val = {
                                'name': product.name,
                                'product_id':
                                    product.product_variant_ids[
                                        0].id,
                                'tax_id': False,
                                'price_unit': -1 * float(
                                    line_item['discount']),
                                'product_uom_qty': 0,
                                'customer_lead': 1,
                            }
                            orderline.append((0, 0, val))
                sale_order.order_line = False
                sale_order.sudo().write(val_list)
                if orderline:
                    sale_order.sudo().write(
                        {'order_line': orderline})
            else:
                self.create_order(data, instance_id)

    def order_data_sync(self):
        """
        Method for syncing order from Woocommerce to Odoo.
        """
        global app
        app = self.get_api()
        page = 1  # The first page number to loop is page 1
        while True:
            order_data = app.get('orders', params={
                'per_page': 100, 'page': page}).json()
            page += 1
            if not order_data:
                break
            else:
                number_of_items = len(
                    list(filter(lambda x: isinstance(x, dict), order_data)))
                model = self.env['ir.model'].search(
                    [('model', '=', "woo.operation")])
                self.env['job.cron'].sudo().create({
                    'model_id': model.id,
                    'function': "write_order_data",
                    'data': order_data,
                    'instance_id': self._context.get('active_id'),
                })
                self.env['woo.logs'].sudo().create({
                    'status': 'success',
                    'description': 'Sync - %s orders has been added to the '
                                   'queue.' % number_of_items,
                    'trigger': 'queue'
                })

    def write_product_data(self, data, instance_id):
        """
        Method for syncing product data.
        :param data: Dictionary of Woocommerce product data.
        :param instance_id: Record set of woo_instance.
        """
        for rec in data:
            # Search for existing product template with the given WooCommerce ID
            prod_id = self.env['product.template'].search([]).filtered(
                lambda r: r.woo_id == str(rec['id']))
            if prod_id:
                # Update existing product based on its type
                if rec.get('type') in ['simple', 'bundle',
                                       'external', 'grouped']:
                    self.write_simple_product(rec, prod_id, instance_id)
                if rec.get('type') == 'variable':
                    self.write_variant_product(rec, prod_id, instance_id)
            else:
                # Create a new product template based on its type
                if rec.get('type') in ['simple', 'bundle',
                                       'external', 'grouped']:
                    self.simple_product_create(rec, instance_id)
                if rec.get('type') == 'variable':
                    self.variant_product_tmpl_create(rec, instance_id)

    def write_simple_product(self, data, product, instance_id):
        """
        Function to write data to a simple WooCommerce product without variants.
        """
        # Prepare values for the product
        val_list = self.prepare_product_vals(data, instance_id)
        # Remove detailed_type from the values
        del val_list['detailed_type']

        # Set instance_id in the values
        val_list['instance_id'] = self._context.get(
            'active_id') if self._context.get('active_id') else False
        # Get product image data
        image = self.get_product_image(data)
        # Get categories from the data
        categories_value = data.get('categories')
        # Set product category in the values
        if categories_value:
            category_woo_id = categories_value[0].get('id')
            category_id = self.env['product.category'].search(
                [('woo_id', '=', category_woo_id)], limit=1)
            if category_id:
                val_list['categ_id'] = category_id.id
        # Set main image in the values
        if image.get('main_image'):
            val_list.update(image.get('main_image'))
        # Set additional images in the values
        if image.get('product_template_image_ids'):
            val_list['product_template_image_ids'] = image.get(
                'product_template_image_ids')
        # Set detailed_type to 'service' if the product is virtual
        if data.get('virtual'):
            val_list['detailed_type'] = 'service'
        # Set optional and alternative products in the values
        val_list['optional_product_ids'] = [
            (6, 0, val_list['optional_product_ids'])]
        val_list['alternative_product_ids'] = [
            (6, 0, val_list['alternative_product_ids'])]
        # Add stock for the product(simple) if manage_stock is enabled
        if data.get('manage_stock') and data.get(
                'stock_quantity') >= 1:
            # add stock for the product(simple)
            stock_variant = self.env[
                'product.product'].sudo().search(
                [('product_tmpl_id', '=', product.id)],
                limit=1)
            existing_stock = self.env[
                'stock.quant'].sudo().search([
                ('product_id', '=', stock_variant.id)])
            if existing_stock:
                existing_stock.sudo().unlink()
            self.env['woo.operation'].sudo().create_stock_vals(stock_variant,
                                                               data)
        # Write the values to the product
        product.write(val_list)

    def write_variant_product(self, data, product, instance_id):
        """
        Function to write a given product with variants.
        """
        app = self.get_api()
        val_list = self.prepare_product_vals(data, instance_id)
        del val_list['detailed_type']
        val_list['instance_id'] = self._context.get(
            'active_id') if self._context.get('active_id') else False
        image = self.get_product_image(data)
        categories_value = data.get('categories')
        # Set product category in the values
        if categories_value:
            category_woo_id = categories_value[0].get('id')
            category_id = self.env['product.category'].search(
                [('woo_id', '=', category_woo_id)], limit=1)
            if category_id:
                val_list['categ_id'] = category_id.id
        if image.get('main_image'):
            val_list.update(image.get('main_image'))
        if image.get('product_template_image_ids'):
            val_list['product_template_image_ids'] = image.get(
                'product_template_image_ids')
        variants_response = []
        try:
            page = 1
            params = {"per_page": 100}
            while True:
                params['page'] = page
                response = app.get("products/%s/variations" % (data.get("id")),
                                   params=params).json()
                page += 1
                if response and isinstance(response, list):
                    variants_response += response
                else:
                    break
        except Exception as error:
            message = "Error While Importing Product Variants from WooCommerce. \n%s" % (
                error)
            return message
        variant_vals = {}
        # intialise to avoid error for products having no variant data.
        if variants_response:
            attribute_lines = product.attribute_line_ids
            attribute_lines.unlink()
            attribute_line_ids = self.get_attribute_line_vals(
                variants_response)
            val_list['attribute_line_ids'] = attribute_line_ids
            variant_vals = self.update_variants(variants_response)
            variant_stock_vals = self.env[
                'woo.operation'].sudo().update_variant_stock_vals(
                variants_response)
        val_list['optional_product_ids'] = [
            (6, 0, val_list['optional_product_ids'])]
        val_list['alternative_product_ids'] = [
            (6, 0, val_list['alternative_product_ids'])]
        product.write(val_list)
        if product:
            for rec in variant_vals:
                if rec['combination']:
                    attr_ids = [attr_id for attr_id in
                                rec[
                                    'combination'].keys()]
                    attr_value_ids = [attr_value_id[0]
                                      for attr_value_id
                                      in
                                      rec['combination'].values()]
                    # Search for product template attribute values
                    domain = [('product_tmpl_id', '=',
                               product.id),
                              ('attribute_id', 'in',
                               attr_ids), (
                                  'product_attribute_value_id',
                                  'in',
                                  attr_value_ids)]
                    product_templ_attr_value = \
                        self.env[
                            'product.template.attribute.value'].sudo().search(
                            domain)
                    product_variant = product.product_variant_ids.filtered(
                        lambda
                            variant: variant.product_template_variant_value_ids.ids == product_templ_attr_value.ids)
                    if product_variant:
                        # Remove the 'combination' key from variant values
                        del rec['combination']
                        # Update the product variant
                        product_variant[0].sudo().write(
                            rec)
        if variant_stock_vals:
            self.env[
                'woo.operation'].sudo().create_stock_variants(
                variant_stock_vals, product)

    def product_data_sync(self):
        """
        Method for syncing product data from Woocommerce to Odoo.
        """
        app = self.get_api()
        page = 1
        while True:
            product_data = app.get('products', params={
                'per_page': 100, 'page': page}).json()
            page += 1
            if not product_data:
                break
            else:
                model = self.env['ir.model'].search(
                    [('model', '=', "woo.operation")])
                self.env['job.cron'].sudo().create({
                    'model_id': model.id,
                    'function': "write_product_data",
                    'data': product_data,
                    'instance_id': self._context.get('active_id'),
                })
                number_of_items = len(
                    list(filter(lambda x: isinstance(x, dict), product_data)))
                self.env['woo.logs'].sudo().create({
                    'status': 'success',
                    'description': 'Sync - %s products has been added to '
                                   'the queue.' % number_of_items,
                    'trigger': 'queue'
                })

    def write_customer(self, data, instance_id):
        """
        Method for syncing customer data, it creates/write customers from
        Woocommerce to Odoo.
       :param data: Dictionary of Woocommerce customer data.
       :param instance_id: Record set woo_instance.
       """
        # Fetch existing partner records with Woo ID
        partner_ids = self.env['res.partner'].search(
            [('woo_id', '!=', False), ('type', '=', 'contact')])

        # Loop through Woocommerce customer data
        for rec in data:
            # Check if partner with Woo ID already exists
            partner_id = partner_ids.filtered(
                lambda r: r.woo_id == str(rec['id']))
            if partner_id:
                # Existing partner found, check and update values if needed
                existing_values = partner_id.read(
                    ['name', 'email', 'woo_id',
                     'woo_user_name', 'company_id'])
                if existing_values[0].get('company_id'):
                    existing_values[0]['company_id'] = \
                        existing_values[0]['company_id'][0]
                existing_values[0].pop("id", None)

                # Extract Woocommerce values for comparison
                woocommerce_values = {
                    'name': rec.get('first_name') + " " + rec.get(
                        'last_name'),
                    'email': rec.get('email'),
                    'woo_id': str(rec.get('id')),
                    'woo_user_name': rec.get('username'),
                    'company_id': self[-1].env.company.id if self[
                        -1].company else False
                }

                # Update partner if Woocommerce values differ
                if not existing_values[0] == woocommerce_values:
                    partner_id.write(woocommerce_values)

                # Process billing address
                if rec.get('billing').get('first_name'):
                    billing_address = {
                        'name': f"{rec['billing'].get('first_name', '').strip()} "
                                f"{rec['billing'].get('last_name', '').strip()}",
                        'phone': rec['billing'].get('phone') or '',
                        'street': rec['billing'].get('address_1') or '',
                        'street2': rec['billing'].get('address_2') or '',
                        'city': rec['billing'].get('city') or '',
                        'zip': rec['billing'].get('postcode') or '',
                        'country_id': self.env['res.country'].sudo().search(
                            [('code', '=', rec['billing']['country'])]).id,
                        'state_id': self.env[
                            'res.country.state'].sudo().search(
                            ['&', ('code', '=', rec['billing']['state']),
                             ('country_id', '=',
                              rec['billing']['country'])]).id if
                        rec['billing']['country'] else False,
                        'type': 'invoice',
                        'instance_id': instance_id.id,
                        'parent_id': partner_id.id,
                    }

                    # Find or create billing partner
                    billing_partner = self.env['res.partner'].sudo().search(
                        [('type', '=', 'invoice'),
                         ('parent_id', '=', partner_id.id)])

                    if billing_partner:
                        billing_partner.sudo().write(billing_address)
                    else:
                        self.env[
                            'res.partner'].create(billing_address)

                    # Process shipping address
                    if rec.get('shipping').get('first_name'):
                        shipping_address = {
                            'name': f"{rec['shipping'].get('first_name', '').strip()} "
                                    f"{rec['shipping'].get('last_name', '').strip()}",
                            'phone': rec['shipping'].get('phone') or '',
                            'street': rec['shipping'].get('address_1') or '',
                            'street2': rec['shipping'].get('address_2') or '',
                            'city': rec['shipping'].get('city') or '',
                            'zip': rec['shipping'].get('postcode') or '',
                            'country_id': self.env[
                                'res.country'].sudo().search(
                                [(
                                 'code', '=', rec['shipping']['country'])]).id,
                            'state_id': self.env[
                                'res.country.state'].sudo().search(
                                ['&', ('code', '=', rec['shipping']['state']),
                                 ('country_id', '=',
                                  rec['shipping']['country'])]).id if
                            rec['shipping']['country'] else False,
                            'type': 'delivery',
                            'instance_id': instance_id.id,
                            'parent_id': partner_id.id,
                        }

                        # Find or create shipping partner
                        shipping_partner = self.env[
                            'res.partner'].sudo().search(
                            [('type', '=', 'delivery'),
                             ('parent_id', '=', partner_id.id)])
                        if shipping_partner:
                            shipping_partner.sudo().write(shipping_address)
                        else:
                            self.env['res.partner'].sudo().create(
                                shipping_address)
            else:
                # Partner not found, create a new customer if email matches the update the customer
                existing_id = self.env['res.partner'].search(
                    [('type', '=', 'contact'),
                     ('email', '=', rec.get('email'))])
                if existing_id:
                    # Existing contact found, update the Woo ID and username
                    if not len(existing_id) > 1:
                        vals = {
                            'woo_id': rec.get('id'),
                            'woo_user_name': rec.get('username'),
                            'instance_id': self._context.get(
                                'active_id') if self._context.get(
                                'active_id') else False,
                            'company_id': self.env.company.id if self.company else False,
                        }
                        if vals:
                            self.env['res.partner'].write(vals)
                else:
                    # No existing contact found, create a new customer
                    self.create_new_customer(rec, instance_id)

    def customer_data_sync(self):
        """
        Method for syncing customer data from Woocommerce to Odoo.
        """
        global app
        app = self.get_api()
        page = 1
        while True:
            customer_data = app.get('customers', params={
                'per_page': 100, 'page': page}).json()
            page += 1
            if not customer_data:
                break
            else:
                number_of_items = len(
                    list(filter(lambda x: isinstance(x, dict), customer_data)))
                model = self.env['ir.model'].search(
                    [('model', '=', "woo.operation")])
                self.env['job.cron'].sudo().create({
                    'model_id': model.id,
                    'function': "write_customer",
                    'data': customer_data,
                    'instance_id': self._context.get('active_id'),
                })
                self.env['woo.logs'].sudo().create({
                    'status': 'success',
                    'description': "Sync - %s customers has been added to "
                                   "the queue." % number_of_items,
                    'trigger': 'queue'
                })

    def get_woo_export(self):
        """
        Method to export data to Woocommerce from Odoo.
        """
        if not (self.product_check or self.order_check or self.customer_check):
            raise UserError(
                _("Please enable at least one Method"))
        if self.order_check:
            self.order_data_export()
        else:
            if self.product_check:
                self.product_data_export()
            if self.customer_check:
                self.customer_data_export()

    def order_data_post(self, data, instance_id):
        """
        Method for posting order data from Odoo to Woocommerce.
        :param data: Dictionary of order data.
        :param instance_id: Record set of woo_instance.
        """
        global app
        app = self.get_api()
        global api_res
        api_res = requests.get(
            'https://api.exchangerate-api.com/v4/latest/' + self[
                -1].currency + '').json()
        for order in data:
            if type(order) == int:
                order_id = self.env['sale.order'].browse(order)
            else:
                order_id = order
            state = 'processing'
            if order_id.state == 'sent':
                state = 'processing'
            elif order_id.state == 'draft':
                state = 'draft'
            elif order_id.state == 'cancel':
                state = 'cancelled'
            elif order_id.state == 'sale':
                state = 'completed'
            if order_id.partner_id.email and not order_id.partner_id.woo_id:
                partner_woo_id = self.create_customer_by_id(
                    order_id.partner_id, order_id, instance_id)
            else:
                partner_woo_id = int(order_id.partner_id.woo_id)
            val_list = {
                'name': order_id.name,
                'customer_id': partner_woo_id,
                'date_created': order_id.date_order.isoformat(),
                'state': state,
                'line_items': [],
            }
            for line in order_id.order_line:
                product_id = line.product_id
                if not product_id.woo_id:
                    self.create_categories_woo()
                    self.create_attributes_woo()
                    self.create_product_tag_woo()
                    self.product_data_post(product_id.product_tmpl_id,
                                           instance_id)
                taxes = []
                if line.tax_id:
                    for tax in line.tax_id:
                        if tax.woo_id:
                            taxes.append({
                                "id": tax.woo_id,
                                "total": "",
                                "subtotal": "",
                            })
                        else:
                            tax_name = tax.name
                            if tax.amount_type == 'percent':
                                tax_rate = tax.amount
                            else:
                                tax_rate = tax.amount / 100
                            data = {
                                "rate": str(tax_rate),
                                "name": tax_name,
                                "shipping": False
                            }
                            a = app.post("taxes", data).json()
                            if a.get('id'):
                                tax.woo_id = a.get('id')
                                tax.instance_id = instance_id.id
                                taxes.append({
                                    "id": tax.woo_id,
                                    "total": "",
                                    "subtotal": "",
                                })

                val_list['line_items'].append({
                    'product_id': product_id.woo_id,
                    'name': product_id.name,
                    'quantity': line.product_uom_qty,
                    'taxes': taxes
                })
            res = app.post('orders', val_list).json()
            if res.get('code'):
                self.env['woo.logs'].sudo().create({
                    'status': 'failed',
                    'trigger': 'export',
                    'description': res.get('message')
                })
            if res.get('id'):
                order_id.woo_id = res.get('id')
                order_id.instance_id = instance_id.id
                self.env['woo.logs'].sudo().create({
                    'status': 'success',
                    'trigger': 'export',
                    'description': 'Sale Order - %s with id - %s is exported '
                                   'successfully' % (
                                       order_id.name, order_id.id)

                })

    def order_data_export(self):
        """
        Method for exporting order datas, it posts products, customers,
        orders from Odoo to Woocommerce.
       """
        global app
        app = self.get_api()
        domain = [('woo_id', '=', False)]
        if self.start_date and self.end_date:
            domain += ('date_order', '>=', self.start_date), (
                'date_order', '<=', self.end_date)
        elif self.start_date:
            domain += [('date_order', '>=', self.start_date)]
        elif self.end_date:
            domain += [('date_order', '<=', self.end_date)]
        order_ids = self.list_records_in_chunks(self.env['sale.order'], domain)
        for chunk in order_ids:
            count_of_item = len(chunk.ids)
            model = self.env['ir.model'].search(
                [('model', '=', "woo.operation")])
            self.env['job.cron'].sudo().create({
                'model_id': model.id,
                'function': "order_data_post",
                'data': chunk.ids,
                'instance_id': self._context.get('active_id'),
            })
            self.env['woo.logs'].sudo().create({
                'status': 'success',
                'description': 'Export - %s orders has been added to the '
                               'queue.' % count_of_item,
                'trigger': 'queue',
            })

    def create_attributes_woo(self):
        """
        Method to create/post attribute and its values from Odoo to
        Woocommerce.
        """
        attributes = self.env['product.attribute'].search(
            [('woo_id', '=', False)])
        attributes_list = []
        for attribute_id in attributes:
            data = {
                "name": attribute_id.name,
                "slug": f'oe_{attribute_id.name}_{attribute_id.id}',
                "type": "select",
                "order_by": "menu_order",
                "has_archives": True,
            }
            att_res = app.post("products/attributes", data).json()
            if att_res.get('code'):
                continue
            elif att_res.get('id') and not att_res.get('code'):
                val = {'id': attribute_id.id, 'woo_id': att_res.get('id'),
                       'instance_id': self._context.get('active_id'),
                       'slug': att_res.get('slug')}
                self.env['woo.logs'].sudo().create({
                    'status': 'success',
                    'trigger': 'export',
                    'description': 'Product Attribute with name - %s and '
                                   'id - %s is exported successfully.' % (
                                       att_res.get('name'), attribute_id.id),
                })
                attributes_list.append(val)
        if attributes_list:
            query = """ UPDATE product_attribute
                        SET woo_id = %(woo_id)s,
                            instance_id = %(instance_id)s,
                            slug = %(slug)s
                        WHERE id = %(id)s
                    """
            self.env.cr.executemany(query, attributes_list)
        attribute_value_ids = self.env['product.attribute.value'].search(
            [('woo_id', '=', False)])
        for attr_value in attribute_value_ids:
            data = {'name': attr_value.name,
                    "slug": f'oe_{attr_value.name}_{attr_value.id}'}
            response = app.post(
                "products/attributes/%s/terms" % attr_value.attribute_id.woo_id,
                data).json()
            if response.get('create'):
                if not response.get('create')[0]['error']:
                    attr_value.write({
                        'woo_id': response.get('create')[0]['id'],
                        'instance_id': self._context.get('active_id'),
                        'slug': response.get('create')[0]['slug']
                    })
                    self.env['woo.logs'].sudo().create({
                        'status': 'success',
                        'trigger': 'export',
                        'description': 'Product Attribute Value with '
                                       'name - %s and id - %s is exported '
                                       'successfully.' % (
                                           attr_value.name, attr_value.id),
                    })
            elif response.get('code'):
                self.env['woo.logs'].sudo().create({
                    'status': 'failed',
                    'trigger': 'export',
                    'description': 'Product Attribute Value with name - %s '
                                   'and id - %s exporting failed. '
                                   'Reason - %s' % (
                                       attr_value.name, attr_value.id,
                                       response.get('message')),
                })
                if response.get('code') == 'term_exists':
                    attr_value.write({
                        'woo_id': response.get('data')['resource_id'],
                        'instance_id': self._context.get('active_id'),
                        'slug': f'oe_{attr_value.name}_{attr_value.id}'
                    })

    def create_categories_woo(self):
        """
        Method for create/post categories from Odoo to Woocommerce.
        """
        categories = self.env['product.category'].search(
            [('woo_id', '=', False)])
        for category_id in categories:
            if category_id.parent_id:
                val = {
                    "name": category_id.name,
                    "parent": category_id.parent_id.woo_id
                }
            else:
                val = {
                    "name": category_id.name,
                }
            res = app.post("products/categories", val).json()
            if not res.get('code'):
                category_id.woo_id = res.get('id')
                category_id.instance_id = self._context.get('active_id')
                self.env['woo.logs'].sudo().create({
                    'status': 'success',
                    'trigger': 'export',
                    'description': 'Category with name - %s and id - %s is '
                                   'exported successfully.' % (
                                       res.get('name'), res.get('id')),
                })
            elif res.get('code'):
                self.env['woo.logs'].sudo().create({
                    'status': 'failed',
                    'trigger': 'export',
                    'description': 'Category with name - %s and id - %s '
                                   'exporting failed. '
                                   'Reason - %s' % (
                                       category_id.name, category_id.id,
                                       res.get('message')),
                })
                if res.get('code') == 'term_exists':
                    category_id.instance_id = self._context.get('active_id') if \
                        res['data'][
                            'resource_id'] else False
                    category_id.woo_id = res['data']['resource_id'] if \
                        res['data']['resource_id'] else False

    def create_product_tag_woo(self):
        """
        Method for creating Woocommerce tags from Odoo.
        """
        tag_ids = self.env['product.tag'].search([('woo_id', '=', False)])
        tag_list = []
        for tag_id in tag_ids:
            data = {
                "name": tag_id.name
            }
            tag_list.append(data)
        if tag_list:
            data = {'create': tag_list}
            response = app.post("products/tags/batch", data).json()
            if response.get('create'):
                tag_ids = tag_ids.mapped('id')
                tag_vals = []
                for index, record in enumerate(response.get('create')):
                    if not record.get('error'):
                        val = {'id': tag_ids[index],
                               'woo_id': record.get('id'),
                               'instance_id': self._context.get('active_id')}
                        tag_vals.append(val)
                    else:
                        tag = self.env['product.tag'].browse(tag_ids[index])
                        self.env['woo.logs'].sudo().create({
                            'status': 'failed',
                            'trigger': 'export',
                            'description': 'Product Tag with name - %s and '
                                           'id - %s exporting failed. '
                                           'Reason - %s' % (tag.name, tag.id,
                                                            record.get(
                                                                'error')[
                                                                'message']),
                        })
                        tag.write({'woo_id': record.get('error')['data'][
                            'resource_id'],
                                   'instance_id': self._context.get(
                                       'active_id')})

                if tag_vals:
                    query = """ UPDATE product_tag SET woo_id = %(woo_id)s WHERE id = %(id)s """
                    self.env.cr.executemany(query, tag_vals)
            elif response.get('code'):
                self.env['woo.logs'].sudo().create({
                    'status': 'failed',
                    'trigger': 'export',
                    'description': 'Product Tag exporting failed. Reason - %s' % (
                        response.get('message')),
                })

    def list_records_in_chunks(self, model, domain=None, chunk_size=50):
        """
        Method for fetching and returning the required records
        as chunks.
       :param model: Environment of the model.
       :param domain: List with tuple values or None.
       :param chunk_size: Integer value.
       :return: Returns record set of the model.
       """
        if domain is None:
            domain = []
        records = model.search(domain)
        chunks = [records[i:i + chunk_size] for i in
                  range(0, len(records), chunk_size)]
        return chunks

    def product_data_post(self, data, instance_id):
        """
        Method for posting product datas from Odoo to Woocommerce.
        :param data: Dictionary of product data.
        :param instance_id: Record set of woo_instance.
        """
        global app
        app = self.get_api()
        for product in data:
            if type(product) == int:
                product_id = self.env['product.template'].browse(product)
            else:
                product_id = product
            product_type = 'variable' if product_id.attribute_line_ids else 'simple'
            description = product_id.description
            tag_list = self.get_product_tag_list(product_id)
            val_list = {
                "name": product_id.name,
                "type": product_type,
                "regular_price": str(self.calc_currency_rate(
                    product_id.list_price, 2)),
                "sku": product_id.default_code if product_id.default_code else "",
                "tags": tag_list,
                "description": description if description else "",
            }
            stock_check = True if product_id.detailed_type == 'product' else False
            if stock_check:
                stock_qty = product_id.qty_available
                val_list.update({
                    'manage_stock': stock_check,
                    'stock_quantity': str(stock_qty),
                })
            else:
                val_list['manage_stock'] = stock_check
            categories = []
            parent = True
            category_id = product_id.categ_id
            while parent:
                categories.append({
                    'id': category_id.woo_id,
                    'name': category_id.name,
                    'slug': category_id.name
                })
                parent = category_id.parent_id
                category_id = parent
            val_list.update({
                "categories": categories
            })
            if product_id.image_1920:
                image_url = self.image_upload(product_id)
                val_list.update({
                    "images": [
                        {
                            "src": image_url
                        },
                    ],
                })
            if product_id.attribute_line_ids:
                attribute_val = []
                for item in product_id.attribute_line_ids:
                    if item.attribute_id.woo_id:
                        attribute_val.append({
                            'id': item.attribute_id.woo_id,
                            'name': item.attribute_id.name,
                            "position": 0,
                            "visible": True,
                            "variation": False,
                            "options": item.value_ids.mapped(
                                'name')
                        })
                val_list.update({
                    'attributes': attribute_val
                })
            if product_id.optional_product_ids:
                cross_sell_ids = [int(item) for item in
                                  product_id.optional_product_ids.mapped(
                                      'woo_id') if
                                  item is not False and item.isdigit()]
                val_list['cross_sell_ids'] = cross_sell_ids

            if product_id.alternative_product_ids:
                upsell_ids = [int(item) for item in
                              product_id.alternative_product_ids.mapped(
                                  'woo_id') if
                              item is not False and item.isdigit()]
                val_list['upsell_ids'] = upsell_ids
            res = app.post("products", val_list).json()
            if res.get('code'):
                self.env['woo.logs'].sudo().create({
                    'status': 'failed',
                    'trigger': 'export',
                    'description': 'Product %s with id %s export failed. '
                                   'Reason - %s' % (
                                       product_id.name, product_id.id,
                                       res.get('message'))
                })
            if res.get('code') == 'woocommerce_product_image_upload_error':
                val_list['images'] = False
                res = app.post("products", val_list).json()
                if res.get('id'):
                    product_id.woo_id = res.get('id')
                    product_id.instance_id = instance_id.id
                    product_id.woo_variant_check = True
                    self.env['woo.logs'].sudo().create({
                        'status': 'success',
                        'trigger': 'export',
                        'description': 'Product %s with id %s exported '
                                       'successfully without image.' % (
                                           product_id.name, product_id.id)
                    })
            elif res.get('id'):
                product_id.woo_id = res.get('id')
                product_id.instance_id = instance_id.id
                product_id.woo_variant_check = True
                self.env['woo.logs'].sudo().create({
                    'status': 'success',
                    'trigger': 'export',
                    'description': 'Product %s with id %s exported '
                                   'successfully.' % (
                                       product_id.name, product_id.id)
                })

    def product_data_export(self):
        """
        Method to export products to Woocommerce.
        """
        global app
        app = self.get_api()
        global api_res
        api_res = requests.get(
            'https://api.exchangerate-api.com/v4/latest/' + self.currency + '').json()
        self.create_categories_woo()
        self.create_attributes_woo()
        self.create_product_tag_woo()
        domain = [('woo_id', '=', False)]
        product_ids = self.list_records_in_chunks(self.env['product.template'],
                                                  domain)
        for chunk in product_ids:
            model = self.env['ir.model'].search(
                [('model', '=', "woo.operation")])
            self.env['job.cron'].sudo().create({
                'model_id': model.id,
                'function': "product_data_post",
                'data': chunk.ids,
                'instance_id': self._context.get('active_id'),
            })
            self.env['woo.logs'].sudo().create({
                'status': 'success',
                'description': 'Export - %s products has been added to '
                               'the queue.' % len(chunk.ids),
                'trigger': 'queue',
            })

    def customer_data_export(self):
        """
        Method to export customer data to Woocommerce.
        """
        domain = [('woo_id', '=', False), ('type', '=', 'contact')]
        customer_ids = self.list_records_in_chunks(self.env['res.partner'],
                                                   domain)
        if customer_ids:
            for chunk in customer_ids:
                count_of_item = len(chunk.ids)
                model = self.env['ir.model'].search(
                    [('model', '=', "woo.operation")])
                self.env['job.cron'].sudo().create({
                    'model_id': model.id,
                    'function': "customer_data_post",
                    'data': chunk.ids,
                    'instance_id': self._context.get('active_id'),
                })
                self.env['woo.logs'].sudo().create({
                    'status': 'success',
                    'description': 'Export - %s customers has been added to '
                                   'the queue.' % count_of_item,
                    'trigger': 'queue',
                })

    def fetch_address(self, vals):
        """
        Method for returning basic customer data.
        :param vals: Dictionary of customer data.
        :returns: The merged key-value pairs.
        """
        name = vals.name if vals.name else vals.parent_id.name
        name = name.rsplit(' ', 1)
        return {
            'first_name': name[0],
            'last_name': name[1] if len(name) > 1 else "",
            'company': "",
            'address_1': vals.street if vals.street else "",
            'address_2': vals.street2 if vals.street2 else "",
            'city': vals.city if vals.city else "",
            'state': vals.state_id.code if vals.state_id.code else "",
            'postcode': vals.zip if vals.zip else "",
            'country': vals.country_id.code if vals.country_id.code else "",
            'email': vals.email if vals.email else vals.parent_id.email,
            'phone': vals.phone if vals.phone else "",
        }

    def customer_data_post(self, data, instance_id):
        """
        Method to export customer data to woo commerce.
        :param data: Dictionary of customer data.
        :param instance_id: Record set of woo_instance.
        """
        # name and email are mandatory
        app = self.get_api()
        value_list = []
        for rec in data:
            if type(rec) == int:
                customer_id = self.env['res.partner'].browse(rec)
            else:
                customer_id = rec
            if customer_id.email:
                # updating the condition as email a mandatory field or
                # skip the current record
                name = customer_id.name.rsplit(' ', 1)
                billing_partner = self.env['res.partner'].sudo().search(
                    [('parent_id', '=', customer_id.id),
                     ('type', '=', 'invoice')],
                    limit=1)
                shipping_partner = self.env['res.partner'].sudo().search(
                    [('parent_id', '=', customer_id.id),
                     ('type', '=', 'delivery')],
                    limit=1)
                default_address = {
                    'first_name': name[0],
                    'last_name': name[1] if len(name) > 1 else "",
                    'company': "",
                    'address_1': customer_id.street if customer_id.street else "",
                    'address_2': customer_id.street2 if customer_id.street2 else "",
                    'city': customer_id.city if customer_id.city else "",
                    'state': customer_id.state_id.code if customer_id.state_id.code else "",
                    'postcode': customer_id.zip if customer_id.zip else "",
                    'country': customer_id.country_id.code if customer_id.country_id.code else "",
                    'email': customer_id.email if customer_id.email else "",
                    'phone': customer_id.phone if customer_id.phone else "",
                }
                data = {
                    "email": customer_id.email,
                    "first_name": name[0],
                    "last_name": name[1] if len(name) > 1 else "",
                    "username": customer_id.email,
                    "role": 'customer',
                    "billing": self.fetch_address(
                        billing_partner) if billing_partner else default_address,
                    "shipping": self.fetch_address(
                        shipping_partner) if shipping_partner else None,
                }
                res = app.post('customers', data).json()
                if res.get('code'):
                    # show the message in instance later
                    self.env['woo.logs'].sudo().create({
                        'status': 'failed',
                        'trigger': 'export',
                        'description': res.get('message')
                    })
                else:
                    val = {'id': customer_id.id, 'woo_id': res.get('id'),
                           'instance_id': instance_id.id,
                           'woo_user_name': res.get('username')}
                    value_list.append(val)
                    self.env['woo.logs'].sudo().create({
                        'status': 'success',
                        'trigger': 'export',
                        'description': 'Customer %s with id - %s exported '
                                       'successfully.' % (
                                           customer_id.name, customer_id.id)
                    })
        if value_list:
            query = """ UPDATE res_partner
                        SET woo_id = %(woo_id)s,instance_id = 
                             %(instance_id)s,
                            woo_user_name = %(woo_user_name)s
                        WHERE id = %(id)s
                    """
            self.env.cr.executemany(query, value_list)

    def create_customer_by_id(self, data, order_id, instance_id):
        """
        Method to export customer data to Woocommerce.
        :param data: Dictionary of customer data.
        :param order_id: Record set of sale_order.
        :param instance_id: Record set of woo_instance.
        :return: Returns id of the record.
        """
        # name and email are mandatory
        app = self.get_api()
        value_list = []
        for rec in data:
            if rec.email:
                # updating the condition as email a mandatory field or
                # skip the current record
                name = rec.name.rsplit(' ', 1)
                billing_partner = self.env['res.partner'].sudo().search(
                    [('parent_id', '=', rec.id), ('type', '=', 'invoice')],
                    limit=1)
                shipping_partner = self.env['res.partner'].sudo().search(
                    [('parent_id', '=', rec.id), ('type', '=', 'delivery')],
                    limit=1)
                default_address = {
                    'first_name': name[0],
                    'last_name': name[1] if len(name) > 1 else "",
                    'company': "",
                    'address_1': rec.street if rec.street else "",
                    'address_2': rec.street2 if rec.street2 else "",
                    'city': rec.city if rec.city else "",
                    'state': rec.state_id.code if rec.state_id.code else "",
                    'postcode': rec.zip if rec.zip else "",
                    'country': rec.country_id.code if rec.country_id.code else "",
                    'email': rec.email if rec.email else "",
                    'phone': rec.phone if rec.phone else "",
                }
                data = {
                    "email": rec.email,
                    "first_name": name[0],
                    "last_name": name[1] if len(name) > 1 else "",
                    "username": rec.email,
                    "role": 'customer',
                    "billing": self.fetch_address(
                        billing_partner) if billing_partner else default_address,
                    "shipping": self.fetch_address(
                        shipping_partner) if shipping_partner else None,
                }
                res = app.post('customers', data).json()
                if res.get('code'):
                    # show the message in instance later
                    self.env['woo.logs'].sudo().create({
                        'status': 'failed',
                        'trigger': 'export',
                        'description': 'Customer %s with Id- %s in the '
                                       'Order - %s export failed. '
                                       'Reason - %s' % (
                                           rec.name, rec.id, order_id.name,
                                           res.get('message'))
                    })
                else:
                    val = {'id': rec.id, 'woo_id': res.get('id'),
                           'instance_id': instance_id.id,
                           'woo_user_name': res.get('username')}
                    value_list.append(val)
                    self.env['woo.logs'].sudo().create({
                        'status': 'success',
                        'trigger': 'export',
                        'description': 'Customer %s with Id- %s in the '
                                       'Order - %s exported successfully.' % (
                                           rec.name, rec.id, order_id.name)
                    })
        if value_list:
            query = """ UPDATE res_partner
                        SET woo_id = %(woo_id)s,
                            instance_id = %(instance_id)s,
                            woo_user_name = %(woo_user_name)s
                        WHERE id = %(id)s
                    """
            self.env.cr.executemany(query, value_list)
        return value_list[0]['woo_id']

    def image_upload(self, product):
        """
        Uploads image into WordPress media to get a public link.
        :param product: Dictionary of product data.
        :return: Returns product url
        """
        attachment_id = self.env['ir.attachment'].sudo().search(
            domain=[('res_model', '=', 'product.template'),
                    ('res_id', '=', product.id),
                    ('res_field', '=', 'image_1920')])
        product_image_url = False
        if attachment_id:
            attachment_id.write({'public': True})
            base_url = self.env['ir.config_parameter'].sudo().get_param(
                'web.base.url')
            product_image_url = f"{base_url}{attachment_id.image_src}.jpg"
        return product_image_url

    # export/update records to woocommerce
    def update_to_woo_commerce(self, instance_id, data, type):
        """
        Method to update/export customer,product,orders data to
           Woocommerce.
           :param data: Dictionary of customer data.
           :param type: Type of the user in the data.
        """
        records = [data[i:i + 50] for i in range(0, len(data), 50)]
        global app
        app = self.get_api()
        global api_res
        api_res = requests.get(
            'https://api.exchangerate-api.com/v4/latest/' + self.currency + '').json()
        if records:
            for chunk in records:
                if type == 'customers':
                    model = self.env['ir.model'].search(
                        [('model', '=', "woo.operation")])
                    self.env['job.cron'].sudo().create({
                        'model_id': model.id,
                        'function': "customer_data_woo_update",
                        'data': chunk.ids,
                        'instance_id': instance_id.id,
                    })
                if type == 'products':
                    self.create_categories_woo()
                    self.create_attributes_woo()
                    self.create_product_tag_woo()
                    model = self.env['ir.model'].search(
                        [('model', '=', "woo.operation")])
                    self.env['job.cron'].sudo().create({
                        'model_id': model.id,
                        'function': "product_data_woo_update",
                        'data': chunk.ids,
                        'instance_id': instance_id.id,
                    })
                if type == 'orders':
                    model = self.env['ir.model'].search(
                        [('model', '=', "woo.operation")])
                    self.env['job.cron'].sudo().create({
                        'model_id': model.id,
                        'function': "order_data_woo_update",
                        'data': chunk.ids,
                        'instance_id': instance_id.id,
                    })

    def customer_data_woo_update(self, data, instance_id):
        """
        Method to update/export customer data to Woocommerce.
        :param data: Dictionary of customer data.
        :param instance_id: Record set of woo_instance
        """
        app = self.get_api()
        value_list = []
        for rec in data:
            if type(rec) == int:
                customer_id = self.env['res.partner'].browse(rec)
            else:
                customer_id = rec
            if customer_id.email:
                # updating the condition as email a mandatory field or
                # skip the current record
                name = customer_id.name.rsplit(' ', 1)
                billing_partner = self.env['res.partner'].sudo().search(
                    [('parent_id', '=', customer_id.id),
                     ('type', '=', 'invoice')],
                    limit=1)
                shipping_partner = self.env['res.partner'].sudo().search(
                    [('parent_id', '=', customer_id.id),
                     ('type', '=', 'delivery')],
                    limit=1)
                default_address = {
                    'first_name': name[0],
                    'last_name': name[1] if len(name) > 1 else "",
                    'company': "",
                    'address_1': customer_id.street if customer_id.street else "",
                    'address_2': customer_id.street2 if customer_id.street2 else "",
                    'city': customer_id.city if customer_id.city else "",
                    'state': customer_id.state_id.code if customer_id.state_id.code else "",
                    'postcode': customer_id.zip if customer_id.zip else "",
                    'country': customer_id.country_id.code if customer_id.country_id.code else "",
                    'email': customer_id.email if customer_id.email else "",
                    'phone': customer_id.phone if customer_id.phone else "",
                }
                data = {
                    "email": customer_id.email,
                    "first_name": name[0],
                    "last_name": name[1] if len(name) > 1 else "",
                    "username": customer_id.email,
                    "role": 'customer',
                    "billing": self.fetch_address(
                        billing_partner) if billing_partner else default_address,
                    "shipping": self.fetch_address(
                        shipping_partner) if shipping_partner else None,
                }
                if not customer_id.woo_id:
                    res = app.post('customers', data).json()
                    if res.get('code'):
                        message = res.get('message')
                    else:
                        val = {'id': customer_id.id, 'woo_id': res.get('id'),
                               'instance_id': instance_id.id,
                               'woo_user_name': res.get('username')}
                        value_list.append(val)
                        customer_id.message_post(
                            body=_(
                                "Customer has been exported to WooCommerce "
                                "with WooCommerce ID: %s." % res.get(
                                    'id'))
                        )
                else:
                    data.pop('username')
                    res = app.put(f"customers/{customer_id.woo_id}",
                                  data).json()
                    if res.get('code'):
                        message = res.get('message')
                    else:
                        val = {'id': customer_id.id, 'woo_id': res.get('id'),
                               'instance_id': instance_id.id,
                               'woo_user_name': res.get('username')}
                        value_list.append(val)
                        customer_id.message_post(
                            body=_(
                                "Customer has been exported to WooCommerce "
                                "with WooCommerce ID: %s." % res.get(
                                    'id'))
                        )

        if value_list:
            query = """ UPDATE res_partner
                                SET woo_id = %(woo_id)s,
                                    instance_id = %(instance_id)s,
                                    woo_user_name = %(woo_user_name)s
                                WHERE id = %(id)s
                            """
            self.env.cr.executemany(query, value_list)

    def product_data_woo_update(self, data, instance_id):
        """
        Method to update/export product data to Woocommerce.
        :param data: Dictionary of product data.
        :param instance_id: Record set of woo_instance.
        """
        app = self.get_api()
        for product in data:
            if type(product) == int:
                product_id = self.env['product.template'].browse(product)
            else:
                product_id = product
            product_type = 'variable' if product_id.attribute_line_ids else 'simple'
            description = product_id.description
            tag_list = self.get_product_tag_list(product_id)
            val_list = {
                "name": product_id.name,
                "type": product_type,
                "regular_price": str(self.calc_currency_rate(
                    product_id.list_price, 2)),
                "sku": product_id.default_code if product_id.default_code else "",
                "description": description if description else "",
                "tags": tag_list,
            }
            stock_check = True if product_id.detailed_type == 'product' else False
            if stock_check:
                stock_qty = product_id.qty_available
                val_list.update({
                    'manage_stock': stock_check,
                    'stock_quantity': str(stock_qty),
                })
            else:
                val_list['manage_stock'] = stock_check
            categories = []
            parent = True
            category_id = product_id.categ_id
            while parent:
                categories.append({
                    'id': category_id.woo_id,
                    'name': category_id.name,
                    'slug': category_id.name
                })
                parent = category_id.parent_id
                category_id = parent
            val_list.update({
                "categories": categories
            })
            if product_id.image_1920:
                image_url = self.image_upload(product_id)
                val_list.update({
                    "images": [
                        {
                            "src": image_url
                        },
                    ],
                })
            if product_id.attribute_line_ids:
                attribute_val = []
                for item in product_id.attribute_line_ids:
                    if item.attribute_id.woo_id:
                        attribute_val.append({
                            'id': item.attribute_id.woo_id,
                            'name': item.attribute_id.name,
                            "position": 0,
                            "visible": True,
                            "variation": True,
                            "options": item.value_ids.mapped(
                                'name')
                        })
                val_list.update({
                    'attributes': attribute_val
                })
            if product_id.optional_product_ids:
                cross_sell_ids = [int(item) for item in
                                  product_id.optional_product_ids.mapped(
                                      'woo_id') if
                                  item is not False and item.isdigit()]
                val_list['cross_sell_ids'] = cross_sell_ids

            if product_id.alternative_product_ids:
                upsell_ids = [int(item) for item in
                              product_id.alternative_product_ids.mapped(
                                  'woo_id') if
                              item is not False and item.isdigit()]
                val_list['upsell_ids'] = upsell_ids
            if not product_id.woo_id:
                res = app.post("products", val_list).json()
                if res.get('code'):
                    self.env['woo.logs'].sudo().create({
                        'status': 'failed',
                        'trigger': 'export',
                        'description': res.get('code')
                    })
                if res.get('code') == 'woocommerce_product_image_upload_error':
                    val_list['images'] = False
                    res = app.post("products", val_list).json()

                if res.get('id'):
                    product_id.woo_id = res.get('id')
                    product_id.instance_id = instance_id.id
                    product_id.woo_variant_check = True
                    product_id.message_post(
                        body=_(
                            "Product has been exported to WooCommerce with"
                            "WooCommerce ID: %s." % res.get(
                                'id')))
            else:
                res = app.put(f"products/{product_id.woo_id}", val_list).json()
                if res.get('code'):
                    self.env['woo.logs'].sudo().create({
                        'status': 'failed',
                        'trigger': 'export',
                        'description': res.get('code')
                    })
                if res.get('code') == 'woocommerce_product_image_upload_error':
                    val_list['images'] = False
                    res = app.post(f"products/{product_id.woo_id}", val_list).json()
                if res.get('id'):
                    product_id.woo_id = res.get('id')
                    product_id.instance_id = instance_id.id
                    product_id.woo_variant_check = True
                    product_id.message_post(
                        body=_(
                            "Product has been exported to WooCommerce with"
                            "WooCommerce ID: %s." % res.get(
                                'id')))

    def get_product_tag_list(self, product_id):
        """
        Method to create list with product tag data.
        :param product_id: Record set of product.
        :return: Returns list of product tag data.
        """
        tag_list = []
        for tag in product_id.product_tag_ids:
            tag_list.append({
                'id': tag.woo_id,
                'name': tag.name,
                'slug': tag.name,
            })
        return tag_list

    def order_data_woo_update(self, data, instance_id):
        """
        Method to update/export orders data to Woocommerce.
        :param data: Dictionary of order data.
        :param instance_id: Record set of woo_instance.
        """
        app = self.get_api()
        for order in data:
            if type(order) == int:
                order_id = self.env['sale.order'].browse(order)
            else:
                order_id = order
            partner_id = order_id.partner_id
            if partner_id.email and not partner_id.woo_id:
                self.customer_data_woo_update([partner_id.id], instance_id)
                partner_id.refresh()
            state = 'processing'
            if order_id.state == 'sent':
                state = 'processing'
            elif order_id.state == 'draft':
                state = 'draft'
            elif order_id.state == 'cancel':
                state = 'cancelled'
            elif order_id.state == 'sale':
                state = 'completed'
            val_list = {
                'name': order_id.name,
                'customer_id': int(order_id.partner_id.woo_id),
                'date_created': order_id.date_order.isoformat(),
                'state': state,
                'line_items': [],
            }
            for line in order_id.order_line:
                product_id = line.product_id
                if not product_id.woo_id:
                    self.create_categories_woo()
                    self.create_attributes_woo()
                    self.create_product_tag_woo()
                    self.product_data_post(product_id.product_tmpl_id,
                                           instance_id)

                taxes = []
                if line.tax_id:
                    for tax in line.tax_id:
                        if tax.woo_id:
                            taxes.append({
                                "id": tax.woo_id,
                                "total": "",
                                "subtotal": "",
                            })
                        else:
                            tax_name = tax.name
                            tax_rate = tax.amount if tax.amount_type == 'percent' else tax.amount / 100
                            data = {
                                "rate": str(tax_rate),
                                "name": tax_name,
                                "shipping": False
                            }
                            a = app.post("taxes", data).json()
                            if a.get('id'):
                                tax.woo_id = a.get('id')
                                tax.instance_id = instance_id
                                taxes.append({
                                    "id": tax.woo_id,
                                    "total": "",
                                    "subtotal": "",
                                })
                val_list['line_items'].append({
                    'product_id': product_id.woo_id,
                    'name': product_id.name,
                    'quantity': line.product_uom_qty,
                    'taxes': taxes,
                })
            if not order_id.woo_id:
                res = app.post('orders', val_list).json()
                if res.get('code'):
                    self.env['woo.logs'].sudo().create({
                        'status': 'failed',
                        'trigger': 'export',
                        'description': res.get('code')
                    })
                if res.get('id'):
                    order_id.woo_id = res.get('id')
                    order_id.instance_id = instance_id
                    order_id.message_post(
                        body=_(
                            "Order has been exported to WooCommerce with "
                            "WooCommerce ID: %s." % res.get(
                                'id'))
                    )
            else:
                res = app.put(f"orders/{order_id.woo_id}", val_list).json()
                if res.get('id'):
                    order_id.woo_id = res.get('id')
                    order_id.instance_id = instance_id
                    order_id.message_post(
                        body=_(
                            "Order has been exported to WooCommerce with "
                            "WooCommerce ID: %s." % res.get(
                                'id'))
                    )
