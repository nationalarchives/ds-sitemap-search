import re

from flask import current_app
from psycopg import sql

STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "been",
        "being",
        "but",
        "by",
        "can",
        "could",
        "did",
        "do",
        "does",
        "doing",
        "for",
        "from",
        "had",
        "has",
        "have",
        "he",
        "her",
        "hers",
        "him",
        "his",
        "how",
        "i",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "may",
        "me",
        "might",
        "more",
        "most",
        "must",
        "my",
        "of",
        "on",
        "or",
        "our",
        "ours",
        "she",
        "should",
        "so",
        "than",
        "that",
        "the",
        "their",
        "theirs",
        "them",
        "then",
        "there",
        "these",
        "they",
        "this",
        "those",
        "through",
        "to",
        "too",
        "under",
        "until",
        "up",
        "us",
        "was",
        "we",
        "were",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "will",
        "with",
        "would",
        "you",
        "your",
    }
)


def get_query_parts(query):
    quoted_query_parts = set()
    query_parts = []
    seen_query_parts = set()
    stop_words_removed = False

    def add_query_part(part, quoted=False):
        nonlocal stop_words_removed
        part = part.lower().strip()
        if not part:
            return
        if part in STOP_WORDS:
            stop_words_removed = True
            return
        if quoted:
            quoted_query_parts.add(part)
        if part not in seen_query_parts:
            seen_query_parts.add(part)
            query_parts.append(part)

    query_start = 0
    for quoted_string in re.finditer(r'"(.*?)"', query):
        unquoted_query = query[query_start : quoted_string.start()]
        for part in unquoted_query.replace('"', "").split(" "):
            add_query_part(part)
        add_query_part(quoted_string.group(1), quoted=True)
        query_start = quoted_string.end()

    unquoted_query = query[query_start:]
    for part in unquoted_query.replace('"', "").split(" "):
        add_query_part(part)

    return query_parts, quoted_query_parts, stop_words_removed


def contruct_search_query(
    all_query_parts,
    quoted_query_parts,
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
            "weight": current_app.config.get("RELEVANCE_DESCRIPTION_MATCH_WEIGHT"),
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

    # Reuse normalised fields for multi-term searches rather than recalculating
    # them for every term.
    prepare_fields = len(all_query_parts) > 1

    # Build a list of SQL sub-queries for each query part to search the fields
    sql_sub_queries = []
    for query_part in all_query_parts:
        sql_sub_query_parts = []
        for field in query_fields:
            field_name = field["field"]
            field_weight = field["weight"]
            sql_sub_query_parts.append(
                sql.SQL("""(
                            CASE WHEN {field} IS NOT NULL THEN (
                                {field_length} -
                                CHAR_LENGTH(REPLACE({lower_field}, {query_part}, ''))
                            ) * {field_weight} ELSE 0 END
                        )""").format(
                    field=sql.Identifier(field_name),
                    field_length=(
                        sql.Identifier(f"{field_name}_length")
                        if prepare_fields
                        else sql.SQL("CHAR_LENGTH({})").format(
                            sql.Identifier(field_name)
                        )
                    ),
                    lower_field=(
                        sql.Identifier(f"{field_name}_lower")
                        if prepare_fields
                        else sql.SQL("LOWER({})").format(sql.Identifier(field_name))
                    ),
                    query_part=sql.Literal(query_part),
                    field_weight=sql.Literal(field_weight),
                )
            )
        sql_sub_queries.append(
            sql.SQL("( ( {part_scores} ) * {weight} )").format(
                part_scores=sql.SQL(" + ").join(sql_sub_query_parts),
                weight=sql.Literal(
                    current_app.config.get("RELEVANCE_QUOTE_MATCH_MULTIPLIER")
                    if query_part in quoted_query_parts
                    else 1
                ),
            )
        )

    blacklisted_urls = current_app.config.get("BLACKLISTED_URLS_SQL_LIKE")
    blacklist_sub_where = (
        sql.SQL("""AND "url" NOT LIKE ALL({blacklisted_url_likes})""").format(
            blacklisted_url_likes=sql.Literal(blacklisted_urls)
        )
        if blacklisted_urls
        else sql.SQL("")
    )

    if prepare_fields:
        prepared_fields = sql.SQL(", ").join(
            sql.SQL(
                "CHAR_LENGTH({field}) AS {field_length}, "
                "LOWER({field}) AS {lower_field}"
            ).format(
                field=sql.Identifier(field["field"]),
                field_length=sql.Identifier(f"{field['field']}_length"),
                lower_field=sql.Identifier(f"{field['field']}_lower"),
            )
            for field in query_fields
        )
        source = sql.SQL(
            '''"sitemap_urls"
            CROSS JOIN LATERAL (
                WITH "prepared_fields" AS MATERIALIZED (
                    SELECT {prepared_fields}
                )
                SELECT * FROM "prepared_fields"
            ) AS "normalised_fields"'''
        ).format(prepared_fields=prepared_fields)
    else:
        source = sql.Identifier("sitemap_urls")

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
                "response_code",
                "date_updated",
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
                        WHEN "url" LIKE {webarchive_domains}
                            OR "response_code" >= 400
                        THEN {archived_weight}
                        ELSE 1
                    END
                ) AS "relevance"
            FROM {source}
            WHERE "url" IS NOT NULL
                {blacklist_sub_where}
        )
        SELECT
            "id",
            "title",
            "url",
            "description",
            "response_code",
            "date_updated",
            "relevance",
            (SELECT COUNT(*) FROM "scored_results" WHERE "relevance" > 0) AS "total_results"
        FROM "scored_results"
        WHERE "relevance" > 0
        ORDER BY "relevance" DESC,
            "title" ASC
        LIMIT {limit}
        OFFSET {offset};""",
    ).format(
        source=source,
        search_sub_query=(
            sql.SQL(" + ").join(sql_sub_queries) if sql_sub_queries else sql.SQL("1")
        ),
        archived_weight=sql.Literal(
            current_app.config.get("RELEVANCE_ARCHIVED_WEIGHT")
        ),
        blacklist_sub_where=blacklist_sub_where,
        limit=sql.Literal(results_per_page),
        offset=sql.Literal((page - 1) * results_per_page),
        webarchive_domains=sql.Literal(
            "|".join([f"{domain}%" for domain in webarchive_domains])
        ),
    )
