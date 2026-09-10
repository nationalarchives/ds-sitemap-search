from flask import request


def cache_key_prefix():
    """Make a key that includes GET parameters."""
    theme = request.cookies.get("theme")
    return f"{request.full_path}{theme if theme in ['light', 'dark', 'system'] else ''}"
