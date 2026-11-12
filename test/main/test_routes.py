import unittest
from unittest.mock import patch

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

    def test_search_treats_plus_as_space(self):
        for query in ("alpha+beta", "alpha%2Bbeta", "alpha%20beta"):
            with (
                self.subTest(query=query),
                patch("app.sitemap_search.routes.psycopg.connect") as connect,
                patch("app.sitemap_search.routes.render_template") as render,
            ):
                connect.return_value.cursor.return_value.fetchall.return_value = []
                render.return_value = "Search results"

                response = self.client.get(f"/search/?q={query}")

                self.assertEqual(response.status_code, 200)
                context = render.call_args.kwargs
                self.assertEqual(context["q"], "alpha beta")
                self.assertEqual(set(context["all_query_parts"]), {"alpha", "beta"})
