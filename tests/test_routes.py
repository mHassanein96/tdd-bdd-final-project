######################################################################
# Copyright 2016, 2023 John J. Rofrano. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
######################################################################
"""
Product API Service Test Suite

Test cases can be run with the following:
  nosetests -v --with-spec --spec-color
  coverage report -m
  codecov --token=$CODECOV_TOKEN

  While debugging just these tests it's convenient to use this:
    nosetests --stop tests/test_service.py:TestProductService
"""
import os
import logging
from decimal import Decimal
from unittest import TestCase
from service import app
from service.common import status
from service.models import db, init_db, Product
from tests.factories import ProductFactory

# Disable all but critical errors during normal test run
# uncomment for debugging failing tests
# logging.disable(logging.CRITICAL)

DATABASE_URI = os.getenv(
    "DATABASE_URI", "postgresql://postgres:postgres@localhost:5432/postgres"
)
BASE_URL = "/products"


######################################################################
#  T E S T   C A S E S
######################################################################
# pylint: disable=too-many-public-methods
class TestProductRoutes(TestCase):
    """Product Service tests"""

    @classmethod
    def setUpClass(cls):
        """Run once before all tests"""
        app.config["TESTING"] = True
        app.config["DEBUG"] = False
        # Set up the test database
        app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URI
        app.logger.setLevel(logging.CRITICAL)
        init_db(app)

    @classmethod
    def tearDownClass(cls):
        """Run once after all tests"""
        db.session.close()

    def setUp(self):
        """Runs before each test"""
        self.client = app.test_client()
        db.session.query(Product).delete()  # clean up the last tests
        db.session.commit()

    def tearDown(self):
        db.session.remove()

    ############################################################
    # Utility function to bulk create products
    ############################################################
    def _create_products(self, count: int = 1) -> list:
        """Factory method to create products in bulk"""
        products = []
        for _ in range(count):
            test_product = ProductFactory()
            response = self.client.post(BASE_URL, json=test_product.serialize())
            self.assertEqual(
                response.status_code,
                status.HTTP_201_CREATED,
                "Could not create test product",
            )
            new_product = response.get_json()
            test_product.id = new_product["id"]
            products.append(test_product)
        return products

    ############################################################
    #  T E S T   C A S E S
    ############################################################
    def test_index(self):
        """It should return the index page"""
        response = self.client.get("/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(b"Product Catalog Administration", response.data)

    def test_health(self):
        """It should be healthy"""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        self.assertEqual(data["message"], "OK")

    # TEST CREATE
    def test_create_product(self):
        """It should Create a new Product"""
        test_product = ProductFactory()
        response = self.client.post(BASE_URL, json=test_product.serialize())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        location = response.headers.get("Location")
        self.assertIsNotNone(location)
        new_product = response.get_json()
        self.assertEqual(new_product["name"], test_product.name)
        self.assertEqual(new_product["description"], test_product.description)
        self.assertEqual(Decimal(new_product["price"]), test_product.price)
        self.assertEqual(new_product["available"], test_product.available)
        self.assertEqual(new_product["category"], test_product.category.name)

        # GET the product using the Location header
        response = self.client.get(location)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        new_product = response.get_json()
        self.assertEqual(new_product["name"], test_product.name)
        self.assertEqual(new_product["description"], test_product.description)
        self.assertEqual(Decimal(new_product["price"]), test_product.price)
        self.assertEqual(new_product["available"], test_product.available)
        self.assertEqual(new_product["category"], test_product.category.name)

    def test_create_product_with_no_name(self):
        """It should not Create a Product without a name"""
        product = self._create_products()[0]
        new_product = product.serialize()
        del new_product["name"]
        response = self.client.post(BASE_URL, json=new_product)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_product_no_content_type(self):
        """It should not Create a Product with no Content-Type"""
        response = self.client.post(BASE_URL, data="bad data")
        self.assertEqual(response.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    def test_create_product_wrong_content_type(self):
        """It should not Create a Product with wrong Content-Type"""
        response = self.client.post(BASE_URL, data={}, content_type="plain/text")
        self.assertEqual(response.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    # TEST READ
    def test_read_a_product(self):
        """It should Read a single Product"""
        product = self._create_products(1)[0]
        response = self.client.get(f"{BASE_URL}/{product.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        self.assertEqual(data["name"], product.name)
        self.assertEqual(data["description"], product.description)

    # TEST UPDATE
    def test_update_a_product(self):
        """It should Update an existing Product"""
        product = self._create_products(1)[0]
        new_name = "Updated Name"
        product.name = new_name
        response = self.client.put(f"{BASE_URL}/{product.id}", json=product.serialize())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        self.assertEqual(data["name"], new_name)

    # TEST UPDATE - NOT FOUND
    def test_update_nonexistent_product_returns_404(self):
        """It should return 404 when trying to update a non-existent Product"""
        non_existent_id = 999999  # An ID unlikely to exist

        # Prepare dummy payload
        dummy_data = {
            "name": "Non-existent",
            "description": "Should not exist",
            "price": "10.00",
            "available": True,
            "category": "MALE",
        }

        response = self.client.put(
            f"{BASE_URL}/{non_existent_id}",
            json=dummy_data,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        data = response.get_json()
        self.assertIn("Product with id", data["message"])
        self.assertIn(str(non_existent_id), data["message"])

    # TEST DELETE
    def test_delete_a_product(self):
        """It should Delete a Product"""
        product = self._create_products(1)[0]
        response = self.client.delete(f"{BASE_URL}/{product.id}")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        response = self.client.get(f"{BASE_URL}/{product.id}")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # TEST LIST ALL
    def test_list_all_products(self):
        """It should List all Products"""
        self._create_products(3)
        response = self.client.get(BASE_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        self.assertEqual(len(data), 3)

    # TEST QUERY
    def test_query_product_by_name(self):
        """It should Query Products by name"""
        products = self._create_products(3)
        target_name = products[0].name
        response = self.client.get(f"{BASE_URL}?name={target_name}")
        self.assertTrue(all(p["name"] == target_name for p in response.get_json()))

    def test_query_product_by_category(self):
        """It should Query Products by category"""
        products = self._create_products(3)
        target_category = products[0].category.name
        response = self.client.get(f"{BASE_URL}?category={target_category}")
        self.assertTrue(
            all(p["category"] == target_category for p in response.get_json())
        )

    def test_query_product_by_availability(self):
        """It should Query Products by availability"""
        products = self._create_products(3)
        target_available = products[0].available
        response = self.client.get(f"{BASE_URL}?available={str(target_available)}")
        self.assertTrue(
            all(p["available"] == target_available for p in response.get_json())
        )
