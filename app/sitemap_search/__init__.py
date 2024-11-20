from flask import Blueprint

bp = Blueprint("sitemap_search", __name__)

from app.sitemap_search import routes  # noqa: E402,F401
