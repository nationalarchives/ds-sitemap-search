import math
import os
from urllib.parse import unquote

import psycopg2
import psycopg2.extras
from app.lib.cache import cache
from app.lib.cache_key_prefix import cache_key_prefix
from app.lib.pagination import pagination_object
from app.sitemap_search import bp
from flask import current_app, render_template, request


@bp.route("/")
@cache.cached(key_prefix=cache_key_prefix)
def index():
    query = unquote(request.args.get("q", "")).strip(" ")
    page = (
        int(request.args.get("page"))
        if request.args.get("page") and request.args.get("page").isnumeric()
        else 1
    )
    results_per_page = 12
    webarchive_domains = current_app.config.get("WEBARCHIVE_REWRITE_DOMAINS")
    conn = psycopg2.connect(
        host=os.environ.get("DB_HOST"),
        database=os.environ.get("DB_NAME"),
        user=os.environ.get("DB_USERNAME"),
        password=os.environ.get("DB_PASSWORD"),
    )
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if query:
        title_match_weight = current_app.config.get(
            "RELEVANCE_TITLE_MATCH_WEIGHT"
        )
        body_match_weight = current_app.config.get(
            "RELEVANCE_BODY_MATCH_WEIGHT"
        )
        archived_weight = current_app.config.get("RELEVANCE_ARCHIVED_WEIGHT")
        cur.execute(
            """WITH scored_results AS (
                SELECT
                    id,
                    title,
                    url,
                    description,
                    (
                        (
                            (
                                CHAR_LENGTH(title) -
                                CHAR_LENGTH(REPLACE(LOWER(title), %(query)s, ''))
                            ) * %(title_match_weight)s
                        ) +
                        (
                            (
                                CHAR_LENGTH(body) -
                                CHAR_LENGTH(REPLACE(LOWER(body), %(query)s, ''))
                            ) * %(body_match_weight)s
                        )
                    ) *
                    (
                        CASE
                            WHEN url LIKE %(webarchive_domains)s THEN %(archived_weight)s
                            ELSE 1
                        END
                    ) AS relevance
                FROM sitemap_urls
                WHERE title IS NOT NULL
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
            LIMIT %(limit)s
            OFFSET %(offset)s;""",
            {
                "query": query.lower(),
                "query_length": len(query),
                "title_match_weight": title_match_weight,
                "body_match_weight": body_match_weight,
                "archived_weight": archived_weight,
                "limit": results_per_page,
                "offset": (page - 1) * results_per_page,
                "webarchive_domains": "|".join(
                    [f"%{domain}%" for domain in webarchive_domains]
                ),
            },
        )
        # return cur.query
        results = cur.fetchall()
        total_results = results[0]["total_results"] if len(results) else 0
        pages = math.ceil(total_results / results_per_page)
        cur.close()
        conn.close()
        if page > 1 and not results:
            return render_template("errors/page-not-found.html")
        return render_template(
            "sitemap_search/index.html",
            q=query,
            page=page,
            pages=pages,
            results=results,
            total_results=total_results,
            results_per_page=results_per_page,
            pagination=pagination_object(page, pages, request.args),
            webarchive_domains=webarchive_domains,
        )
    else:
        cur.execute("SELECT COUNT(*) AS total_results FROM sitemap_urls")
        results = cur.fetchall()
        total_results = results[0]["total_results"] if len(results) else 0
        return render_template(
            "sitemap_search/index.html",
            q=query,
            page=page,
            pages=0,
            results=[],
            total_results=total_results,
            results_per_page=results_per_page,
            pagination={},
            webarchive_domains=webarchive_domains,
        )
