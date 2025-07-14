import math
import os
import re
from urllib.parse import unquote

import psycopg2
import psycopg2.extras
from app.lib.cache import cache
from app.lib.cache_key_prefix import cache_key_prefix
from app.lib.pagination import pagination_object
from app.sitemap_search import bp
from flask import current_app, render_template, request
from psycopg2 import sql


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

    # Get the query
    query = unquote(request.args.get("q", "")).strip()

    # Get the requested page number, default to 1 if not provided or invalid
    page = (
        int(request.args.get("page"))
        if request.args.get("page") and request.args.get("page").isnumeric()
        else 1
    )
    results_per_page = current_app.config.get("RESULTS_PER_PAGE")

    # Get the web archive domains from the config - this is used to determine if a URL
    # is archived and should have a different relevance weight
    webarchive_domains = current_app.config.get("ARCHIVE_REMAP").keys()

    # Start a connection to the database and create a cursor
    conn = psycopg2.connect(
        host=os.environ.get("DB_HOST"),
        database=os.environ.get("DB_NAME"),
        user=os.environ.get("DB_USERNAME"),
        password=os.environ.get("DB_PASSWORD"),
    )
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # If there is a query, we need to search the database
    if query:
        # Create an empty set to hold quoted query parts
        # This is used to give more weight to exact matches in quotes
        quoted_query_parts = set()

        # Split the query into parts, handling quoted strings separately
        discected_query = query
        while quoted_strings := re.search(r"(\"(.*?)\")", discected_query):
            quoted_query_parts.add(quoted_strings.group(2).lower().strip())
            discected_query = discected_query.replace(
                quoted_strings.group(0), ""
            ).strip()

        # Create a set of query parts with quoted and unquoted parts
        query_parts = quoted_query_parts.union(
            set(discected_query.replace('"', "").lower().split(" "))
        )
        query_parts = [part for part in list(query_parts) if part]
        # query_parts.sort()

        # Define the fields we want to query and their realtive weights
        query_fields = [
            {
                "field": "title",
                "weight": current_app.config.get(
                    "RELEVANCE_TITLE_MATCH_WEIGHT"
                ),
            },
            {
                "field": "body",
                "weight": current_app.config.get("RELEVANCE_BODY_MATCH_WEIGHT"),
            },
            {
                "field": "url",
                "weight": current_app.config.get("RELEVANCE_URL_MATCH_WEIGHT"),
            },
        ]

        # Build a list of SQL sub-queries for each query part to search the fields
        sql_sub_queries = []
        for query_part in query_parts:
            sql_sub_query_parts = []
            for field in query_fields:
                field_name = field["field"]
                weight = field["weight"]
                sql_sub_query_parts.append(
                    sql.SQL(
                        """(
                                (
                                    CHAR_LENGTH({field}) -
                                    CHAR_LENGTH(REPLACE(LOWER({field}), {query_part}, ''))
                                ) * {weight}
                            )"""
                    ).format(
                        field=sql.Identifier(field_name),
                        query_part=sql.Literal(query_part),
                        # Multiply the weight by a multiplier if the query part is quoted
                        weight=sql.Literal(
                            weight
                            * (
                                current_app.config.get(
                                    "RELEVANCE_QUOTE_MATCH_MULTIPLIER"
                                )
                                if query_part in quoted_query_parts
                                else 1
                            )
                        ),
                    )
                )
            sql_sub_queries.append(sql.SQL(" + ").join(sql_sub_query_parts))

        # Add a sub-query to filter by types if requested
        types_sub_query = sql.SQL("")
        requested_types = request.args.get("types", "all")
        if requested_types == "research-guides":
            types_sub_query = sql.SQL(
                "AND url LIKE '%/help-with-your-research/research-guides/%'"
            )
        elif requested_types == "archived-blog-posts":
            types_sub_query = sql.SQL(
                "AND url LIKE 'https://blog.nationalarchives.gov.uk/%'"
            )

        # Create the main SQL query to fetch the results
        sql_query = sql.SQL(
            """WITH scored_results AS (
                SELECT
                    id,
                    title,
                    url,
                    description,
                    (
                        {search_sub_query}
                    ) *
                    (
                        CASE
                            WHEN url LIKE {webarchive_domains} THEN {archived_weight}
                            ELSE 1
                        END
                    ) AS relevance
                FROM sitemap_urls
                WHERE title IS NOT NULL {types_sub_query}
            )
            SELECT
                id,
                title,
                url,
                description,
                relevance,
                (SELECT COUNT(*) FROM scored_results WHERE relevance > 0) AS total_results
            FROM scored_results
            WHERE relevance > 0
            ORDER by relevance DESC
            LIMIT {limit}
            OFFSET {offset};""",
        ).format(
            search_sub_query=sql.SQL(" + ").join(sql_sub_queries),
            archived_weight=sql.Literal(
                current_app.config.get("RELEVANCE_ARCHIVED_WEIGHT")
            ),
            types_sub_query=types_sub_query,
            limit=sql.Literal(results_per_page),
            offset=sql.Literal((page - 1) * results_per_page),
            webarchive_domains=sql.Literal(
                "|".join([f"%{domain}%" for domain in webarchive_domains])
            ),
        )
        cur.execute(sql_query)
        # return cur.query

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
        cur.execute("SELECT COUNT(*) AS total_results FROM sitemap_urls")
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
