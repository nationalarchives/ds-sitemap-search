import logging

import sentry_sdk
from app.lib.cache import cache
from app.lib.context_processor import cookie_preference, now_iso_8601
from app.lib.talisman import talisman
from app.lib.template_filters import (
    commafy,
    mark,
    pretty_age,
    result_type,
    slugify,
)
from app.lib.urls import correct_url, is_url_archived
from flask import Flask
from jinja2 import ChoiceLoader, PackageLoader
from tna_utilities.datetime import pretty_datetime


def create_app(config_class):
    app = Flask(__name__, static_url_path="/search/static")
    app.config.from_object(config_class)

    if app.config.get("SENTRY_DSN"):
        sentry_sdk.init(
            dsn=app.config.get("SENTRY_DSN"),
            environment=app.config.get("ENVIRONMENT_NAME"),
            release=(
                f"ds-sitemap-search@{app.config.get('BUILD_VERSION')}"
                if app.config.get("BUILD_VERSION")
                else ""
            ),
            sample_rate=app.config.get("SENTRY_SAMPLE_RATE"),
            traces_sample_rate=app.config.get("SENTRY_SAMPLE_RATE"),
            profiles_sample_rate=app.config.get("SENTRY_SAMPLE_RATE"),
        )

    gunicorn_error_logger = logging.getLogger("gunicorn.error")
    app.logger.handlers.extend(gunicorn_error_logger.handlers)
    app.logger.setLevel(gunicorn_error_logger.level or "DEBUG")

    cache.init_app(
        app,
        config={
            "CACHE_TYPE": app.config.get("CACHE_TYPE"),
            "CACHE_DEFAULT_TIMEOUT": app.config.get("CACHE_DEFAULT_TIMEOUT"),
            "CACHE_IGNORE_ERRORS": app.config.get("CACHE_IGNORE_ERRORS"),
            "CACHE_DIR": app.config.get("CACHE_DIR"),
        },
    )

    csp_self = "'self'"
    csp_none = "'none'"
    default_csp = csp_self
    csp_rules = {
        key.replace("_", "-"): value
        for key, value in app.config.get_namespace(
            "CSP_", lowercase=True, trim_namespace=True
        ).items()
        if not key.startswith("feature_") and value not in [None, [default_csp]]
    }
    talisman.init_app(
        app,
        content_security_policy={
            "default-src": default_csp,
            "base-uri": csp_none,
            "object-src": csp_none,
        }
        | csp_rules,
        content_security_policy_report_uri=app.config.get(
            "CSP_REPORT_URL", None
        ),
        force_https=app.config["FORCE_HTTPS"],
    )

    @app.after_request
    def apply_extra_headers(response):
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        response.headers["Cross-Origin-Embedder-Policy"] = "unsafe-none"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        return response

    app.jinja_env.trim_blocks = True
    app.jinja_env.lstrip_blocks = True
    app.jinja_loader = ChoiceLoader(
        [
            PackageLoader("app"),
            PackageLoader("tna_frontend_jinja"),
        ]
    )

    app.add_template_filter(commafy)
    app.add_template_filter(correct_url)
    app.add_template_filter(is_url_archived)
    app.add_template_filter(mark)
    app.add_template_filter(pretty_age)
    app.add_template_filter(pretty_datetime)
    app.add_template_filter(result_type)
    app.add_template_filter(slugify)

    @app.context_processor
    def context_processor():
        return dict(
            cookie_preference=cookie_preference,
            now_iso_8601=now_iso_8601,
            app_config={
                "ENVIRONMENT": app.config.get("ENVIRONMENT"),
                "CONTAINER_IMAGE": app.config.get("CONTAINER_IMAGE"),
                "BUILD_VERSION": app.config.get("BUILD_VERSION"),
                "TNA_FRONTEND_VERSION": app.config.get("TNA_FRONTEND_VERSION"),
                "COOKIE_DOMAIN": app.config.get("COOKIE_DOMAIN"),
                "GA4_ID": app.config.get("GA4_ID"),
            },
            feature={
                "PHASE_BANNER": app.config.get("FEATURE_PHASE_BANNER"),
            },
        )

    from .healthcheck import bp as healthcheck_bp
    from .main import bp as site_bp
    from .sitemap_search import bp as sitemap_search_bp

    app.register_blueprint(site_bp)
    app.register_blueprint(healthcheck_bp, url_prefix="/healthcheck")
    app.register_blueprint(sitemap_search_bp, url_prefix="/search")

    return app
