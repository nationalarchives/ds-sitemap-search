from app.lib.cache import cache
from app.lib.cache_key_prefix import cache_key_prefix
from app.main import bp
from flask import render_template


@bp.route("/")
@cache.cached(key_prefix=cache_key_prefix)
def index():
    return render_template("main/index.html")


@bp.route("/cookies/")
@cache.cached(key_prefix=cache_key_prefix)
def cookies():
    return render_template("main/cookies.html")
