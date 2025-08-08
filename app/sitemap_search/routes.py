import math
import os
from urllib.parse import unquote

import psycopg2
import psycopg2.extras
from app.lib.cache import cache
from app.lib.cache_key_prefix import cache_key_prefix
from app.lib.pagination import pagination_object
from app.lib.sql import contruct_search_query, get_query_parts
from app.sitemap_search import bp
from flask import current_app, render_template, request


@bp.route("/")
# @cache.cached(key_prefix=cache_key_prefix)
def index():
    """
    Search the sitemap database for URLs matching the query.

    This is a simple and "hacky" search implementation that constructs a complex SQL
    query to search the database of previously crawled pages.

    It is a temporary solution until we can implement a more robust search solution
    using Wagtail.
    """

    # Get the query and remove any asterisks or leading/trailing whitespace as
    # asterisks will break the search query
    query = unquote(request.args.get("q", "")).replace("*", "").strip()

    # Get the requested types from the query parameters, default to "all" if not provided
    # or invalid. This is used to filter the results by type, e.g. research guides
    requested_types = request.args.get("types", "all")

    # Get the requested page number, default to 1 if not provided or invalid
    page = (
        int(request.args.get("page"))
        if request.args.get("page") and request.args.get("page").isnumeric()
        else 1
    )
    results_per_page = current_app.config.get("RESULTS_PER_PAGE")

    # Start a connection to the database and create a cursor
    conn = psycopg2.connect(
        host=os.environ.get("DB_HOST"),
        database=os.environ.get("DB_NAME"),
        user=os.environ.get("DB_USERNAME"),
        password=os.environ.get("DB_PASSWORD"),
    )
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # If there is a query, we need to search the database
    if query or requested_types != "all":
        query_parts, quoted_query_parts = get_query_parts(query)
        sql_query = contruct_search_query(query, requested_types)
        cur.execute(sql_query)

        # Get all the results
        results = cur.fetchall()

        # Close the cursor and connection
        cur.close()
        conn.close()

        # Get the total number of results and calculate the pages required for
        # pagination
        total_results = results[0]["total_results"] if len(results) else 0
        pages = math.ceil(total_results / results_per_page)

        # If there are no results and the page is greater than 1, return a 404
        if not results and page > 1:
            return render_template("errors/page-not-found.html")

        # Render the template with the results
        return render_template(
            "sitemap_search/index.html",
            q=query,
            query_parts=query_parts,
            page=page,
            pages=pages,
            results=results,
            total_results=total_results,
            results_per_page=results_per_page,
            pagination=pagination_object(page, pages, request.args),
        )
    else:
        # If there is no query, we just return the index page with no results
        sql_query = psycopg2.sql.SQL(
            """
                    SELECT COUNT(*) AS total_results
                    FROM sitemap_urls
                    WHERE url NOT LIKE ANY({blacklisted_url_likes})"""
        ).format(
            blacklisted_url_likes=psycopg2.sql.Literal(
                current_app.config.get("BLACKLISTED_URLS_SQL_LIKE")
            )
        )
        cur.execute(sql_query)
        results = cur.fetchall()

        # Close the cursor and connection
        cur.close()
        conn.close()

        # Get the total number of results
        total_results = results[0]["total_results"] if len(results) else 0

        # Render the template with no results
        return render_template(
            "sitemap_search/index.html",
            q=query,
            page=page,
            pages=0,
            results=[],
            total_results=total_results,
            results_per_page=results_per_page,
            pagination={},
        )
