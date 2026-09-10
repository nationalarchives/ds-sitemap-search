import re
from urllib.parse import quote_plus

from app.lib.urls import correct_url, is_url_archived


def commafy(s):
    return f"{s:,}"


def remove_quotes(s):
    return s.replace('"', "").replace("'", "")


def result_type(url):
    url = correct_url(url)
    if is_url_archived(url):
        return "Archived"
    if "/help-with-your-research/research-guides/" in url:
        return "Research guide"
    return ""


def mark(s, substrings):
    substrings = (
        substrings
        if isinstance(substrings, list)
        else [
            re.escape(string.replace('"', "").strip())
            for string in substrings.split(" ")
            if string
        ]
    )
    substrings = [re.escape(quote_plus(string)) for string in substrings if string]
    compiled = re.compile(f"({'|'.join(substrings)})", re.IGNORECASE)
    return compiled.sub(r"<mark>\g<0></mark>", s)
