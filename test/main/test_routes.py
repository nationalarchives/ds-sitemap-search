import unittest

from app import create_app


class MainBlueprintTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app("config.Test")
        self.client = self.app.test_client()
        self.domain = "http://localhost"

    def test_homepage(self):
        rv = self.client.get("/")
        self.assertEqual(rv.status_code, 200)
        self.assertIn('<h1 class="tna-heading-xl">TNA Flask application</h1>', rv.text)
