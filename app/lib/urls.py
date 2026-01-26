from config import ARCHIVED_URLS, DOMAIN_REMAPS
import json
import os

def correct_url(url):
    remaps = DOMAIN_REMAPS | (
        json.loads(os.environ.get("DOMAIN_REMAPS", "{}"))
    )
    for domain, replacement in remaps.items():
        if url.startswith(domain):
            return url.replace(domain, replacement)
    return url


def is_url_archived(url):
    archived_urls: list[str] = [
        domain
        for domain in (
            ARCHIVED_URLS
            + [
                archived_url
                for archived_url in os.environ.get("ARCHIVED_URLS", "").split(
                    ","
                )
                if archived_url
            ]
        )
        if domain
    ]
    for archived_url in archived_urls:
        if url.startswith(archived_url):
            return True
    return False
