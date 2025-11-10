import re

from flask import current_app
from psycopg2 import sql


def get_query_parts(query):
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

    return query_parts, quoted_query_parts


def contruct_search_query(
    all_query_parts,
    quoted_query_parts,
    requested_types,
    page=1,
    results_per_page=12,
):
    # Define the fields we want to query and their realtive weights
    query_fields = [
        {
            "field": "title",
            "weight": current_app.config.get("RELEVANCE_TITLE_MATCH_WEIGHT"),
        },
        {
            "field": "description",
            "weight": current_app.config.get(
                "RELEVANCE_DESCRIPTION_MATCH_WEIGHT"
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
    for query_part in all_query_parts:
        sql_sub_query_parts = []
        for field in query_fields:
            field_name = field["field"]
            weight = field["weight"]
            sql_sub_query_parts.append(
                sql.SQL(
                    """(
                            CASE WHEN {field} IS NOT NULL THEN (
                                CHAR_LENGTH({field}) -
                                CHAR_LENGTH(REPLACE(LOWER({field}), {query_part}, ''))
                            ) * {weight} ELSE 0 END
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
    if requested_types == "research-guides":
        types_sub_query = sql.SQL(
            """
            AND "url" LIKE '%/help-with-your-research/research-guides/%'
            AND "url" NOT LIKE '%/help-with-your-research/research-guides/'
            """
        )
    elif requested_types == "archived-blog-posts":
        types_sub_query = sql.SQL(
            """AND "url" LIKE 'https://blog.nationalarchives.gov.uk/%'"""
        )
    elif requested_types == "education-and-outreach":
        types_sub_query = sql.SQL(
            """AND "url" LIKE '%.nationalarchives.gov.uk/education/%'"""
        )

    blacklisted_urls = current_app.config.get("BLACKLISTED_URLS_SQL_LIKE")
    blacklist_sub_where = (
        sql.SQL("""AND "url" NOT LIKE ALL({blacklisted_url_likes})""").format(
            blacklisted_url_likes=sql.Literal(blacklisted_urls)
        )
        if blacklisted_urls
        else sql.SQL("")
    )

    # Get the web archive domains from the config - this is used to determine if a URL
    # is archived and should have a different relevance weight
    webarchive_domains = current_app.config.get("ARCHIVED_URLS")

    # Create the main SQL query to fetch the results
    return sql.SQL(
        """WITH "scored_results" AS (
            SELECT
                "id",
                "title",
                "url",
                "description",
                (
                    (
                        {search_sub_query}
                    ) /
                    (
                        (
                            CHAR_LENGTH(url) -
                            CHAR_LENGTH(REPLACE(url, '/', ''))
                        ) + 1
                    )
                ) *
                (
                    CASE
                        WHEN "url" LIKE {webarchive_domains} THEN {archived_weight}
                        ELSE 1
                    END
                ) AS "relevance"
            FROM "sitemap_urls"
            WHERE "url" IS NOT NULL
                {blacklist_sub_where}
                {types_sub_query}
        )
        SELECT
            "id",
            "title",
            "url",
            "description",
            "relevance",
            (SELECT COUNT(*) FROM "scored_results" WHERE "relevance" > 0) AS "total_results"
        FROM "scored_results"
        WHERE "relevance" > 0
        ORDER BY "relevance" DESC,
            "title" ASC
        LIMIT {limit}
        OFFSET {offset};""",
    ).format(
        search_sub_query=(
            sql.SQL(" + ").join(sql_sub_queries)
            if sql_sub_queries
            else sql.SQL("1")
        ),
        archived_weight=sql.Literal(
            current_app.config.get("RELEVANCE_ARCHIVED_WEIGHT")
        ),
        blacklist_sub_where=blacklist_sub_where,
        types_sub_query=types_sub_query,
        limit=sql.Literal(results_per_page),
        offset=sql.Literal((page - 1) * results_per_page),
        webarchive_domains=sql.Literal(
            "|".join([f"{domain}%" for domain in webarchive_domains])
        ),
    )
