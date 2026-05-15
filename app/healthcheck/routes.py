from flask import current_app

from app.healthcheck import bp


@bp.route("/live/")
def healthcheck():
    return "ok"


@bp.route("/version/")
def healthcheck_version():
    return current_app.config["BUILD_VERSION"]
