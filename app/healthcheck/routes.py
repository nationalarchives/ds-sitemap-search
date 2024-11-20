from app.healthcheck import bp


@bp.route("/live/")
def healthcheck():
    return "ok"
