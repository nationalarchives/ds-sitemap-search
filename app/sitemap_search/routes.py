import math
import os
from urllib.parse import unquote

import psycopg2
import psycopg2.extras
from app.lib.pagination import pagination_object
from app.sitemap_search import bp
from flask import render_template, request


@bp.route("/")
def index():
    query = unquote(request.args.get("q", "")).strip(" ").lower()
    page = (
        int(request.args.get("page"))
        if request.args.get("page") and request.args.get("page").isnumeric()
        else 1
    )
    results_per_page = 12
    conn = psycopg2.connect(
        host=os.environ.get("DB_HOST"),
        database=os.environ.get("DB_NAME"),
        user=os.environ.get("DB_USERNAME"),
        password=os.environ.get("DB_PASSWORD"),
    )
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if query:
        title_score = 5
        description_score = 3
        url_score = 2
        body_instance_score = 1
        cur.execute(
            """WITH scored_results AS (
                SELECT
                    id,
                    title,
                    url,
                    description,
                    (%(title_score)s * ((CHAR_LENGTH(title) - CHAR_LENGTH(REPLACE(LOWER(title), %(query)s, ''))) / CHAR_LENGTH(%(query)s))) +
                    /*(%(description_score)s * ((CHAR_LENGTH(description) - CHAR_LENGTH(REPLACE(LOWER(description), %(query)s, ''))) / CHAR_LENGTH(%(query)s))) +*/
                    /*(%(url_score)s * ((CHAR_LENGTH(url) - CHAR_LENGTH(REPLACE(LOWER(url), %(query)s, ''))) / CHAR_LENGTH(%(query)s))) +*/
                    (%(body_instance_score)s * ((CHAR_LENGTH(body) - CHAR_LENGTH(REPLACE(LOWER(body), %(query)s, ''))) / CHAR_LENGTH(%(query)s))) AS relevance
                FROM sitemap_urls
                WHERE title IS NOT NULL
            ), filtered_scored_results AS (
                SELECT
                    id,
                    title,
                    url,
                    description,
                    relevance
                FROM scored_results
            )
            SELECT
                id,
                title,
                url,
                description,
                relevance,
                (SELECT COUNT(*) FROM filtered_scored_results WHERE relevance > 0) AS total_results
            FROM filtered_scored_results
            WHERE relevance > 0
            ORDER by relevance DESC
            LIMIT %(limit)s
            OFFSET %(offset)s;""",
            {
                "query": query,
                "title_score": title_score,
                "url_score": url_score,
                "description_score": description_score,
                "body_instance_score": body_instance_score,
                "limit": results_per_page,
                "offset": (page - 1) * results_per_page,
            },
        )
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
        )
