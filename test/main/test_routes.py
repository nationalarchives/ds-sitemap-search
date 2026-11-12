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
                self.assertEqual(context["all_query_parts"], ["alpha", "beta"])

    def test_search_omits_stop_words_before_constructing_sql(self):
        with (
            patch("app.sitemap_search.routes.psycopg.connect") as connect,
            patch("app.sitemap_search.routes.render_template") as render,
        ):
            connect.return_value.cursor.return_value.fetchall.return_value = []
            render.return_value = "Search results"

            response = self.client.get("/search/?q=the+history+and+of+archives")

            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                render.call_args.kwargs["all_query_parts"],
                ["history", "archives"],
            )
            self.assertTrue(render.call_args.kwargs["stop_words_removed"])

    def test_search_preserves_quoted_terms_in_query_order(self):
        with (
            patch("app.sitemap_search.routes.psycopg.connect") as connect,
            patch("app.sitemap_search.routes.render_template") as render,
        ):
            connect.return_value.cursor.return_value.fetchall.return_value = []
            render.return_value = "Search results"

            response = self.client.get(
                "/search/?q=the+history+%22national+archives%22+and+records"
            )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                render.call_args.kwargs["all_query_parts"],
                ["history", "national archives", "records"],
            )

    def test_search_with_only_stop_words_does_not_match_everything(self):
        with patch("app.sitemap_search.routes.contruct_search_query") as build_query:
            response = self.client.get("/search/?q=the+and+of")

            self.assertEqual(response.status_code, 200)
            build_query.assert_not_called()
            self.assertIn("Common words such as", response.text)
            self.assertIn("have been ignored to help focus your search.", response.text)
