import re
from datetime import datetime

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


def pretty_age(date):
    if not date:
        raise ValueError("Date must be provided")

    now = datetime.now()
    delta = now - date
    days = delta.days
    seconds = delta.seconds

    if seconds < 0:
        prefix = "In "
        suffix = ""
    else:
        prefix = ""
        suffix = " ago"

    if days > 365:
        years = days // 365
        return f"{prefix}{years} year{'s' if years != 1 else ''}{suffix}"
    elif days > 30:
        months = days // 30
        return f"{prefix}{months} month{'s' if months != 1 else ''}{suffix}"
    elif days > 0:
        return f"{prefix}{days} day{'s' if days != 1 else ''}{suffix}"
    elif seconds > 3600:
        hours = seconds // 3600
        return f"{prefix}{hours} hour{'s' if hours != 1 else ''}{suffix}"
    elif seconds > 60:
        minutes = seconds // 60
        return f"{prefix}{minutes} minute{'s' if minutes != 1 else ''}{suffix}"
    else:
        return f"{prefix}{seconds} second{'s' if seconds != 1 else ''}{suffix}"
