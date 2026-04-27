import unittest

from app import create_app


class MainBlueprintTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app("config.Test")
        self.client = self.app.test_client()
        self.domain = "http://localhost"

    def test_healthcheck_live(self):
        rv = self.client.get("/healthcheck/live/")
        self.assertEqual(rv.status_code, 200)
        self.assertIn("ok", rv.text)

    def test_trailing_slash_redirects(self):
        rv = self.client.get("/healthcheck/live")
        self.assertEqual(rv.status_code, 308)
        self.assertEqual(rv.location, f"{self.domain}/healthcheck/live/")

    def test_healthcheck_version(self):
        rv = self.client.get("/healthcheck/version/")
        self.assertEqual(rv.status_code, 200)
        self.assertIn(self.app.config.get("BUILD_VERSION", ""), rv.text)
