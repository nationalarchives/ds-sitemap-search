import re


def slugify(s):
    s = s.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s)
    s = re.sub(r"^-+|-+$", "", s)
    return s


def commafy(s):
    return "{:,}".format(s)


def mark(s, substring):
    compiled = re.compile(f"({substring})", re.IGNORECASE)
    return compiled.sub(r"<mark>\g<0></mark>", s)
