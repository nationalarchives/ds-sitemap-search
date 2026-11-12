from app.lib.template_filters import mark


def test_mark_matches_quoted_phrases_and_individual_terms():
    text = "National Archives and archives"

    assert mark(text, ["archives", "national archives"]) == (
        "<mark>National Archives</mark> and <mark>archives</mark>"
    )


def test_mark_does_not_nest_individual_terms_inside_quoted_phrases():
    text = "The National Archives"
    term_orders = (
        ["national archives", "national", "archives"],
        ["archives", "national", "national archives"],
    )

    for terms in term_orders:
        result = mark(text, terms)

        assert result == "The <mark>National Archives</mark>"
        assert result.count("<mark>") == 1
        assert result.count("</mark>") == 1


def test_mark_matches_quoted_phrases_in_urls():
    assert mark("/search?q=national+archives", ["national archives"]) == (
        "/search?q=<mark>national+archives</mark>"
    )
    assert mark("/search?q=national%20archives", ["national archives"]) == (
        "/search?q=<mark>national%20archives</mark>"
    )
