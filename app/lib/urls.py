from config import ARCHIVE_REMAP, DOMAIN_REMAPS


def correct_url(url):
    for domain, replacement in DOMAIN_REMAPS.items():
        if url.startswith(domain):
            return url.replace(domain, replacement)
    return url


def use_archived_url(url):
    for domain, replacement in ARCHIVE_REMAP.items():
        if url.startswith(domain):
            return url.replace(domain, replacement)
    return url


def is_url_archived(url):
    for archive_domain in ARCHIVE_REMAP.keys():
        if url.startswith(archive_domain):
            return True
    return False
