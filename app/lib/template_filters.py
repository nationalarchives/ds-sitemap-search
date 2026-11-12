import re
from urllib.parse import quote_plus

from app.lib.urls import correct_url, is_url_archived


def commafy(s):
    return f"{s:,}"


def remove_quotes(s):
    return s.replace('"', "").replace("'", "")


def result_type(url, response_code=0):
    url = correct_url(url)
    if is_url_archived(url) or (response_code and response_code >= 400):
        return "Archived"
    if "/help-with-your-research/research-guides/" in url:
        return "Research guide"
    return ""


def mark(s, substrings):
    if not isinstance(substrings, list):
        substrings = [
            string.replace('"', "").strip()
            for string in substrings.split(" ")
            if string.strip()
        ]

    patterns = []
    for substring in substrings:
        substring = substring.strip()
        if not substring:
            continue

        encoded_substring = quote_plus(substring)
        pattern = re.escape(encoded_substring)
        if " " in substring:
            words = substring.split()
            text_phrase = r"\s+".join(re.escape(word) for word in words)
            plus_encoded_phrase = re.escape(encoded_substring)
            percent_encoded_phrase = re.escape(encoded_substring.replace("+", "%20"))
            pattern = (
                f"(?:{text_phrase}|{plus_encoded_phrase}|{percent_encoded_phrase})"
            )
        patterns.append((len(substring), pattern))

    if not patterns:
        return s

    patterns.sort(key=lambda item: item[0], reverse=True)
    compiled = re.compile(
        f"({'|'.join(pattern for _, pattern in patterns)})", re.IGNORECASE
    )
    return compiled.sub(r"<mark>\g<0></mark>", s)
