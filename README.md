# Sitemap Search

## Quickstart

```sh
# Build and start the container
docker compose up -d
```

### Add the static assets

During the first time install, your `app/static/assets` directory will be empty.

As you mount the project directory to the `/app` volume, the static assets from TNA Frontend installed inside the container will be "overwritten" by your empty directory.

To add back in the static assets, run:

```sh
docker compose exec app cp -r /app/node_modules/@nationalarchives/frontend/nationalarchives/assets /app/app/static
```

### Population

```sh
# Populate all pages from sitemaps and update existing entries
docker compose exec app poetry run python populate.py

# Process a specific sitemap
docker compose exec app poetry run python populate.py https://blog.nationalarchives.gov.uk/sitemap.xml

# Add new URLs but don't update existing ones
docker compose exec app poetry run python add_new.py

# Add new URLs from a specific sitemap
docker compose exec app poetry run python add_new.py https://blog.nationalarchives.gov.uk/sitemap.xml

# Drop all URLs and re-index - THIS IS A DESTRUCTIVE ACTION
docker compose exec app poetry run python clean.py
```

### Run tests

```sh
docker compose exec dev poetry run python -m pytest
```

### Format and lint code

```sh
docker compose exec dev format
```

## Environment variables

In addition to the [base Docker image variables](https://github.com/nationalarchives/docker/blob/main/docker/tna-python/README.md#environment-variables), this application has support for:

| Variable                             | Purpose                                                                     | Default                                                   |
| ------------------------------------ | --------------------------------------------------------------------------- | --------------------------------------------------------- |
| `CONFIG`                             | The configuration to use                                                    | `config.Production`                                       |
| `DEBUG`                              | If true, allow debugging[^1]                                                | `False`                                                   |
| `SENTRY_DSN`                         | The Sentry DSN (project code)                                               | _none_                                                    |
| `SENTRY_SAMPLE_RATE`                 | How often to sample traces and profiles (0-1.0)                             | production: `0.1`, staging: `1`, develop: `0`, test: `0`  |
| `COOKIE_DOMAIN`                      | The domain to save cookie preferences against                               | _none_                                                    |
| `CSP_IMG_SRC`                        | A comma separated list of CSP rules for `img-src`                           | `'self'`                                                  |
| `CSP_SCRIPT_SRC`                     | A comma separated list of CSP rules for `script-src`                        | `'self'`                                                  |
| `CSP_SCRIPT_SRC_ELEM`                | A comma separated list of CSP rules for `script-src-elem`                   | `'self'`                                                  |
| `CSP_STYLE_SRC`                      | A comma separated list of CSP rules for `style-src`                         | `'self'`                                                  |
| `CSP_STYLE_SRC_ELEM`                 | A comma separated list of CSP rules for `style-src-elem`                    | `'self'`                                                  |
| `CSP_FONT_SRC`                       | A comma separated list of CSP rules for `font-src`                          | `'self'`                                                  |
| `CSP_CONNECT_SRC`                    | A comma separated list of CSP rules for `connect-src`                       | `'self'`                                                  |
| `CSP_MEDIA_SRC`                      | A comma separated list of CSP rules for `media-src`                         | `'self'`                                                  |
| `CSP_WORKER_SRC`                     | A comma separated list of CSP rules for `worker-src`                        | `'self'`                                                  |
| `CSP_FRAME_SRC`                      | A comma separated list of CSP rules for `frame-src`                         | `'self'`                                                  |
| `CSP_FEATURE_FULLSCREEN`             | A comma separated list of rules for the `fullscreen` feature policy         | `'self'`                                                  |
| `CSP_FEATURE_PICTURE_IN_PICTURE`     | A comma separated list of rules for the `picture-in-picture` feature policy | `'self'`                                                  |
| `FORCE_HTTPS`                        | Redirect requests to HTTPS as part of the CSP                               | _none_                                                    |
| `CACHE_TYPE`                         | https://flask-caching.readthedocs.io/en/latest/#configuring-flask-caching   | _none_                                                    |
| `CACHE_DEFAULT_TIMEOUT`              | The number of seconds to cache pages for                                    | production: `300`, staging: `60`, develop: `1`, test: `0` |
| `CACHE_DIR`                          | Directory for storing cached responses when using `FileSystemCache`         | `/tmp`                                                    |
| `GA4_ID`                             | The Google Analytics 4 ID                                                   | _none_                                                    |
| `RELEVANCE_TITLE_MATCH_WEIGHT`       | The score to use for every query match in the title                         | `50`                                                      |
| `RELEVANCE_DESCRIPTION_MATCH_WEIGHT` | The score to use for every query match in the description                   | `10`                                                      |
| `RELEVANCE_BODY_MATCH_WEIGHT`        | The score to use for every query match in the body                          | `2`                                                       |
| `RELEVANCE_URL_MATCH_WEIGHT`         | The score to use for every query match in the page URL                      | `1`                                                       |
| `RELEVANCE_ARCHIVED_WEIGHT`          | The multiplier to use for a result with a URL in `ARCHIVED_URLS`            | `0.5`                                                     |
| `RELEVANCE_QUOTE_MATCH_MULTIPLIER`   | The multiplier to use for a result that matches a quoted string             | `250`                                                     |
| `DOMAIN_REMAPS`                      | A JSON dict of remapped URLs (e.g. for fixing `http://website.live.local/`) | _See `DOMAIN_REMAPS` in `config.py`_                      |
| `ARCHIVED_URLS`                      | A CSV list of archived URLs                                                 | _See `ARCHIVED_URLS` in `config.py`_                      |
| `BLACKLISTED_URLS_SQL_LIKE`          | A CSV list of URLs to exclude from search results                           | _See `config.py`_                                         |
| `RESULTS_PER_PAGE`                   | The number of results to show on a page                                     | `12`                                                      |

[^1] [Debugging in Flask](https://flask.palletsprojects.com/en/2.3.x/debugging/)
