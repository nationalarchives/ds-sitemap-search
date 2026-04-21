from app.healthcheck import bp
from flask import current_app


@bp.route("/live/")
def healthcheck():
    return "ok"


@bp.route("/version/")
def healthcheck_version():
    return current_app.config["BUILD_VERSION"]
