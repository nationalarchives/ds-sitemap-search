import math
import os
import unicodedata
from urllib.parse import unquote

import psycopg
from flask import current_app, redirect, render_template, request, url_for
from psycopg.rows import dict_row

from app.lib.cache import cache
from app.lib.cache_key_prefix import cache_key_prefix
from app.lib.pagination import pagination_object
from app.lib.sql import contruct_search_query, get_query_parts
from app.sitemap_search import bp


@bp.route("/")
@cache.cached(key_prefix=cache_key_prefix)
def index():
    """
    Search the sitemap database for URLs matching the query.

    This is a simple and "hacky" search implementation that constructs a complex SQL
    query to search the database of previously crawled pages.

    It is a temporary solution until we can implement a more robust search solution
    using Wagtail.
    """

    # Get the query from the query parameters
    query = unquote(request.args.get("q", "")).replace("+", " ")

    # Normalise the query to remove any special characters
    query = (
        unicodedata.normalize("NFKD", query).encode("ascii", "ignore").decode("ascii")
    )

    # Remove any asterisks or leading/trailing whitespace
    query = query.replace("*", "").strip()

    # Get the requested page number, default to 1 if not provided or invalid
    page = (
        int(request.args.get("page"))
        if request.args.get("page") and request.args.get("page").isnumeric()
        else 1
    )
    results_per_page = current_app.config.get("RESULTS_PER_PAGE")

    if query:
        all_query_parts, quoted_query_parts, stop_words_removed = get_query_parts(query)

        if not all_query_parts:
            return render_template(
                "sitemap_search/index.html",
                q=query,
                all_query_parts=[],
                num_query_parts_exceeded=False,
                stop_words_removed=stop_words_removed,
                page=page,
                pages=0,
                results=[],
                total_results=0,
                results_per_page=results_per_page,
                pagination={},
            )

    # Start a connection to the database and create a cursor
    conn = psycopg.connect(
        host=os.environ.get("DB_HOST"),
        dbname=os.environ.get("DB_NAME"),
        user=os.environ.get("DB_USERNAME"),
        password=os.environ.get("DB_PASSWORD"),
    )
    cur = conn.cursor(row_factory=dict_row)

    # If there is a query, we need to search the database
    if query:
        # Get the maximum number of query parts allowed
        max_query_parts = current_app.config.get("MAX_QUERY_PARTS")

        # Check if the number of query parts exceeds the maximum allowed and
        # trim the list if necessary, preferring quoted parts
        num_query_parts_exceeded = False
        if len(all_query_parts) > max_query_parts:
            num_query_parts_exceeded = True
            if len(quoted_query_parts) >= max_query_parts:
                all_query_parts = [
                    part for part in all_query_parts if part in quoted_query_parts
                ][:max_query_parts]
                quoted_query_parts = set(all_query_parts)
            else:
                unquoted_query_parts = [
                    part for part in all_query_parts if part not in quoted_query_parts
                ]
                included_query_parts = set(quoted_query_parts).union(
                    unquoted_query_parts[: max_query_parts - len(quoted_query_parts)]
                )
                all_query_parts = [
                    part for part in all_query_parts if part in included_query_parts
                ]

        # Construct and execute the SQL query
        sql_query = contruct_search_query(
            all_query_parts=all_query_parts,
            quoted_query_parts=quoted_query_parts,
            page=page,
            results_per_page=results_per_page,
        )
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
            all_query_parts=all_query_parts,
            num_query_parts_exceeded=num_query_parts_exceeded,
            stop_words_removed=stop_words_removed,
            page=page,
            pages=pages,
            results=results,
            total_results=total_results,
            results_per_page=results_per_page,
            pagination=pagination_object(page, pages, request.args),
        )
    else:
        # If there is no query, we just return the index page with no results
        sql_query = psycopg.sql.SQL("""
                    SELECT COUNT(*) AS total_results,
                        MAX(date_updated) AS last_updated
                    FROM sitemap_urls
                    WHERE url NOT LIKE ANY({blacklisted_url_likes})""").format(
            blacklisted_url_likes=psycopg.sql.Literal(
                current_app.config.get("BLACKLISTED_URLS_SQL_LIKE")
            )
        )
        cur.execute(sql_query)
        results = cur.fetchall()

        # Close the cursor and connection
        cur.close()
        conn.close()

        # Get the total number of results and last updated date
        total_results = results[0]["total_results"] if len(results) else 0
        last_updated = results[0]["last_updated"] if len(results) else None

        # Render the template with no results
        return render_template(
            "sitemap_search/index.html",
            q=query,
            page=page,
            pages=0,
            results=[],
            total_results=total_results,
            last_updated=last_updated,
            results_per_page=results_per_page,
            pagination={},
        )


@bp.route("/results")
def old_results():
    query = request.args.get("_q", "")
    return redirect(url_for("sitemap_search.index", q=query))
