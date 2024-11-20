from flask import Blueprint

bp = Blueprint("healthcheck", __name__)

from app.healthcheck import routes  # noqa: E402,F401
