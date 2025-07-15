from config import ARCHIVED_URLS, DOMAIN_REMAPS


def correct_url(url):
    for domain, replacement in DOMAIN_REMAPS.items():
        if url.startswith(domain):
            return url.replace(domain, replacement)
    return url


def is_url_archived(url):
    for archived_url in ARCHIVED_URLS:
        if url.startswith(archived_url):
            return True
    return False
