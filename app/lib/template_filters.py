import re


def slugify(s):
    s = s.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s)
    s = re.sub(r"^-+|-+$", "", s)
    return s


def commafy(s):
    return "{:,}".format(s)


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
