import json
from datetime import UTC, datetime
from urllib.parse import unquote

from flask import request


def now_iso_8601():
    now = datetime.now(UTC)
    now_date = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    return now_date


def cookie_preference(policy):
    if "cookie_preferences" in request.cookies:
        cookie_preferences = request.cookies["cookie_preferences"]
        preferences = json.loads(unquote(cookie_preferences))
        return preferences.get(policy, None)
    return None
