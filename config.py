import json
import os

from app.lib.util import strtobool

DOMAIN_REMAPS = {
    "http://website.live.local/": "https://www.nationalarchives.gov.uk/",
    "http://website.staging.local/": "https://staging-www.nationalarchives.gov.uk/",
    "http://website.dev.local/": "https://dev-www.nationalarchives.gov.uk/",
}
ARCHIVED_URLS = [
    "https://blog.nationalarchives.gov.uk/",
]


class Features:
    FEATURE_PHASE_BANNER: bool = strtobool(
        os.getenv("FEATURE_PHASE_BANNER", "True")
    )


class Production(Features):
    ENVIRONMENT_NAME: str = os.environ.get("ENVIRONMENT_NAME", "production")

    CONTAINER_IMAGE: str = os.environ.get("CONTAINER_IMAGE", "")
    BUILD_VERSION: str = os.environ.get("BUILD_VERSION", "")
    TNA_FRONTEND_VERSION: str = ""
    try:
        with open(
            os.path.join(
                os.path.realpath(os.path.dirname(__file__)),
                "node_modules/@nationalarchives/frontend",
                "package.json",
            )
        ) as package_json:
            try:
                data = json.load(package_json)
                TNA_FRONTEND_VERSION = data["version"] or ""
            except ValueError:
                pass
    except FileNotFoundError:
        pass

    SECRET_KEY: str = os.environ.get("SECRET_KEY", "")

    DEBUG: bool = strtobool(os.getenv("DEBUG", "False"))

    SENTRY_DSN: str = os.getenv("SENTRY_DSN", "")
    SENTRY_SAMPLE_RATE: float = float(os.getenv("SENTRY_SAMPLE_RATE", "0.1"))

    COOKIE_DOMAIN: str = os.environ.get("COOKIE_DOMAIN", "")

    CSP_IMG_SRC: list[str] = os.environ.get("CSP_IMG_SRC", "'self'").split(",")
    CSP_SCRIPT_SRC: list[str] = os.environ.get(
        "CSP_SCRIPT_SRC", "'self'"
    ).split(",")
    CSP_SCRIPT_SRC_ELEM: list[str] = os.environ.get(
        "CSP_SCRIPT_SRC_ELEM", "'self'"
    ).split(",")
    CSP_STYLE_SRC: list[str] = os.environ.get("CSP_STYLE_SRC", "'self'").split(
        ","
    )
    CSP_STYLE_SRC_ELEM: list[str] = os.environ.get(
        "CSP_STYLE_SRC_ELEM", "'self'"
    ).split(",")
    CSP_FONT_SRC: list[str] = os.environ.get("CSP_FONT_SRC", "'self'").split(
        ","
    )
    CSP_CONNECT_SRC: list[str] = os.environ.get(
        "CSP_CONNECT_SRC", "'self'"
    ).split(",")
    CSP_MEDIA_SRC: list[str] = os.environ.get("CSP_MEDIA_SRC", "'self'").split(
        ","
    )
    CSP_WORKER_SRC: list[str] = os.environ.get(
        "CSP_WORKER_SRC", "'self'"
    ).split(",")
    CSP_FRAME_SRC: list[str] = os.environ.get("CSP_FRAME_SRC", "'self'").split(
        ","
    )
    CSP_FEATURE_FULLSCREEN: list[str] = os.environ.get(
        "CSP_FEATURE_FULLSCREEN", "'self'"
    ).split(",")
    CSP_FEATURE_PICTURE_IN_PICTURE: list[str] = os.environ.get(
        "CSP_FEATURE_PICTURE_IN_PICTURE", "'self'"
    ).split(",")
    FORCE_HTTPS: bool = strtobool(os.getenv("FORCE_HTTPS", "True"))

    CACHE_TYPE: str = "FileSystemCache"
    CACHE_DEFAULT_TIMEOUT: int = int(
        os.environ.get("CACHE_DEFAULT_TIMEOUT", "300")
    )
    CACHE_IGNORE_ERRORS: bool = True
    CACHE_DIR: str = os.environ.get("CACHE_DIR", "/tmp")

    GA4_ID: str = os.environ.get("GA4_ID", "")

    DOMAIN_REMAPS: dict = DOMAIN_REMAPS | (
        json.loads(os.environ.get("DOMAIN_REMAPS", "{}"))
    )
    ARCHIVED_URLS: list[str] = [
        domain
        for domain in (
            ARCHIVED_URLS
            + [
                archived_url
                for archived_url in os.environ.get("ARCHIVED_URLS", "").split(
                    ","
                )
                if archived_url
            ]
        )
        if domain
    ]

    RELEVANCE_TITLE_MATCH_WEIGHT: float = float(
        os.environ.get("RELEVANCE_TITLE_MATCH_WEIGHT", "250")
    )
    RELEVANCE_DESCRIPTION_MATCH_WEIGHT: float = float(
        os.environ.get("RELEVANCE_DESCRIPTION_MATCH_WEIGHT", "50")
    )
    RELEVANCE_URL_MATCH_WEIGHT: float = float(
        os.environ.get("RELEVANCE_URL_MATCH_WEIGHT", "5")
    )
    RELEVANCE_BODY_MATCH_WEIGHT: float = float(
        os.environ.get("RELEVANCE_BODY_MATCH_WEIGHT", "1")
    )
    RELEVANCE_ARCHIVED_WEIGHT: float = float(
        os.environ.get("RELEVANCE_ARCHIVED_WEIGHT", "0.5")
    )
    RELEVANCE_QUOTE_MATCH_MULTIPLIER: float = float(
        os.environ.get("RELEVANCE_QUOTE_MATCH_MULTIPLIER", "1000")
    )

    BLACKLISTED_URLS_SQL_LIKE: list[str] = [
        blacklisted_url
        for blacklisted_url in os.environ.get(
            "BLACKLISTED_URLS_SQL_LIKE",
            "",
        ).split(",")
        if blacklisted_url
    ] or [
        "%nationalarchives.gov.uk/tag/%",
        "%nationalarchives.gov.uk/im_guidance_link/%",
        "%nationalarchives.gov.uk/category/new-chat/%",
        "%nationalarchives.gov.uk/category/records-2/%",
    ]

    RESULTS_PER_PAGE: int = int(os.environ.get("RESULTS_PER_PAGE", "12"))


class Staging(Production, Features):
    SENTRY_SAMPLE_RATE = float(os.getenv("SENTRY_SAMPLE_RATE", "1"))

    CACHE_DEFAULT_TIMEOUT = int(os.environ.get("CACHE_DEFAULT_TIMEOUT", "60"))


class Develop(Production, Features):
    SENTRY_SAMPLE_RATE = float(os.getenv("SENTRY_SAMPLE_RATE", "0"))

    CACHE_DEFAULT_TIMEOUT = int(os.environ.get("CACHE_DEFAULT_TIMEOUT", "1"))


class Test(Production, Features):
    ENVIRONMENT_NAME = "test"

    DEBUG = True
    TESTING = True
    EXPLAIN_TEMPLATE_LOADING = True

    SENTRY_DSN = ""
    SENTRY_SAMPLE_RATE = 0

    CACHE_TYPE = "SimpleCache"
    CACHE_DEFAULT_TIMEOUT = 1

    FORCE_HTTPS = False
