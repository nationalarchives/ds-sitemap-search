import re

from app.lib.urls import correct_url, is_url_archived


def slugify(s):
    s = s.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s)
    s = re.sub(r"^-+|-+$", "", s)
    return s


def commafy(s):
    return "{:,}".format(s)


def result_type(url):
    url = correct_url(url)
    if is_url_archived(url):
        return "Archived"
    if "/help-with-your-research/research-guides/" in url:
        return "Research guide"
    # if "/education/resources/" in url:
    #     return "Education resource"
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
    compiled = re.compile(f"({"|".join(substrings)})", re.IGNORECASE)
    return compiled.sub(r"<mark>\g<0></mark>", s)
