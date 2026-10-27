import runpy
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import pytest
import requests
from flask import Flask
from psycopg.rows import dict_row
from sqlalchemy import create_engine, event, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import populate
from app.lib import database
from app.lib.sql import contruct_search_query
from app.models import SitemapURL

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def db(monkeypatch):
    schema = f"test_indexing_{uuid4().hex}"
    with database.engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    test_engine = create_engine(
        database.engine.url,
        connect_args={"options": f"-csearch_path={schema}"},
    )

    original_engine = database.engine
    monkeypatch.setattr(database, "engine", test_engine)
    monkeypatch.setattr(populate, "engine", test_engine)
    try:
        yield test_engine
    finally:
        test_engine.dispose()
        with original_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))


@pytest.fixture
def ready_db(db):
    database.create_database()
    return db


def stored(db, url):
    with Session(db) as session:
        return session.scalar(select(SitemapURL).where(SitemapURL.url == url))


def response(status=200, body="<title>Page</title><main>Content</main>"):
    result = requests.Response()
    result.status_code = status
    result._content = body.encode()
    result._content_consumed = True
    return result


def test_schema_upgrade_preserves_existing_data(db):
    with db.begin() as connection:
        connection.execute(
            text(
                """
            CREATE TABLE sitemap_urls (
                id INTEGER PRIMARY KEY,
                title VARCHAR(500),
                url VARCHAR(500) NOT NULL UNIQUE,
                description TEXT,
                body TEXT,
                date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                date_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
            )
        )
        connection.execute(
            text(
                """
            INSERT INTO sitemap_urls (id, url, title)
            VALUES (1, 'https://example.com/', 'Existing')
        """
            )
        )
    database.create_database()
    entry = stored(db, "https://example.com/")
    assert entry.title == "Existing"
    assert entry.response_code is None
    assert "response_code" in {
        column["name"] for column in inspect(db).get_columns("sitemap_urls")
    }


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("status", [200, 404, 500])
def test_indexing_stores_status_and_preserves_failed_content(
    ready_db, existing, status
):
    url = "https://example.com/"
    if existing:
        with Session(ready_db) as session, session.begin():
            session.add(
                SitemapURL(
                    url=url,
                    title="Old",
                    body="Old body",
                    description="Old description",
                    response_code=200,
                )
            )
    http = Mock()
    http.get.return_value = response(status)
    indexer = populate.PageIndexer(http, 1, {url} if existing else set())
    indexer((0, url))
    entry = stored(ready_db, url)
    assert entry.response_code == status
    assert entry.date_updated is not None
    assert entry.date_added is not None
    if status == 200:
        assert entry.title == "Page"
        assert entry.body == "Content"
        assert entry.description is None
    elif existing:
        assert (entry.title, entry.body, entry.description) == (
            "Old",
            "Old body",
            "Old description",
        )
    else:
        assert entry.title is None
        assert entry.body is None
    assert url in indexer.existing_urls


def test_status_is_updated_when_content_and_code_are_unchanged(ready_db):
    url = "https://example.com/"
    with Session(ready_db) as session, session.begin():
        session.add(
            SitemapURL(url=url, response_code=404, date_updated=datetime(2000, 1, 1))
        )
    http = Mock()
    http.get.return_value = response(404)
    populate.PageIndexer(http, 1, {url})((0, url))
    assert stored(ready_db, url).date_updated > datetime(2000, 1, 1)


@pytest.mark.parametrize("existing", [False, True])
def test_network_failure_leaves_previous_state(ready_db, existing, capsys):
    url = "https://example.com/"
    if existing:
        with Session(ready_db) as session, session.begin():
            session.add(SitemapURL(url=url, response_code=200))
    http = Mock()
    http.get.side_effect = requests.Timeout("Timed out")
    populate.PageIndexer(http, 1, {url} if existing else set())((0, url))
    entry = stored(ready_db, url)
    assert (entry.response_code if entry else None) == (200 if existing else None)
    assert "Timed out" in capsys.readouterr().out


def test_skip_existing_checks_canonical_url(ready_db, monkeypatch):
    monkeypatch.setenv(
        "DOMAIN_REMAPS", '{"https://old.example/": "https://example.com/"}'
    )
    http = Mock()
    populate.PageIndexer(http, 1, {"https://example.com/"}, True)(
        (0, "https://old.example/")
    )
    http.get.assert_not_called()


def test_update_remapped_url_without_duplicates(ready_db, monkeypatch):
    monkeypatch.setenv(
        "DOMAIN_REMAPS", '{"https://old.example/": "https://example.com/"}'
    )
    with Session(ready_db) as session, session.begin():
        session.add(SitemapURL(url="https://old.example/", title="Old"))
        session.add(SitemapURL(url="https://example.com/", title="Canonical"))
    http = Mock()
    http.get.return_value = response()
    populate.PageIndexer(http, 1, set())((0, "https://old.example/"))
    assert stored(ready_db, "https://old.example/") is None
    assert stored(ready_db, "https://example.com/").title == "Page"


def test_domain_maintenance_preserves_canonical_record(ready_db, monkeypatch):
    monkeypatch.setenv(
        "DOMAIN_REMAPS", '{"https://old.example/": "https://example.com/"}'
    )
    with Session(ready_db) as session, session.begin():
        session.add_all(
            [
                SitemapURL(url="https://old.example/", title="Duplicate"),
                SitemapURL(
                    url="https://example.com/",
                    title="Canonical",
                    response_code=201,
                ),
                SitemapURL(url="https://old.example/new", response_code=404),
            ]
        )
    populate.fix_remapped_domains()
    assert stored(ready_db, "https://old.example/") is None
    assert stored(ready_db, "https://example.com/").title == "Canonical"
    assert stored(ready_db, "https://example.com/").response_code == 201
    assert stored(ready_db, "https://example.com/new").response_code == 404


def test_process_creates_database_and_reuses_http_session(db, monkeypatch):
    urls = ["https://example.com/one", "https://example.com/two"]
    monkeypatch.setattr(populate, "get_urls_from_sitemap", Mock(return_value=urls))
    http = Mock()
    http.get.side_effect = [response(200), response(404)]
    manager = Mock()
    manager.__enter__ = Mock(return_value=http)
    manager.__exit__ = Mock(return_value=False)
    factory = Mock(return_value=manager)
    monkeypatch.setattr(populate.requests, "Session", factory)
    populate.process_sitemap("https://example.com/sitemap.xml")
    factory.assert_called_once_with()
    assert http.get.call_count == 2
    assert stored(db, urls[0]).response_code == 200
    assert stored(db, urls[1]).response_code == 404


def test_database_failure_rolls_back_and_is_not_silenced(ready_db):
    http = Mock()
    http.get.return_value = response()
    indexer = populate.PageIndexer(http, 1, set())

    def reject_insert(connection, cursor, statement, parameters, context, many):
        if statement.startswith("INSERT"):
            raise IntegrityError(statement, parameters, Exception("DB failed"))

    event.listen(ready_db, "before_cursor_execute", reject_insert)
    try:
        with pytest.raises(IntegrityError):
            indexer((0, "https://example.com/"))
    finally:
        event.remove(ready_db, "before_cursor_execute", reject_insert)
    assert stored(ready_db, "https://example.com/") is None
    assert not indexer.existing_urls
    http.get.return_value = response()
    indexer((0, "https://example.com/"))
    assert stored(ready_db, "https://example.com/").response_code == 200


def test_existing_search_query_reads_model_created_table(ready_db):
    with Session(ready_db) as session, session.begin():
        session.add_all(
            [
                SitemapURL(
                    title="Needle",
                    url="https://example.com/one",
                    response_code=200,
                ),
                SitemapURL(
                    title="Other",
                    body="needle",
                    url="https://example.com/two",
                    response_code=500,
                ),
                SitemapURL(url="https://example.com/error", response_code=404),
            ]
        )
    app = Flask(__name__)
    app.config.from_object("config.Test")
    with app.app_context():
        query = contruct_search_query(["needle"], set(), "all", results_per_page=1)
    connection = ready_db.raw_connection()
    try:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(query)
            results = cursor.fetchall()
    finally:
        connection.close()
    assert len(results) == 1
    assert results[0]["title"] == "Needle"
    assert results[0]["total_results"] == 2
    assert results[0]["relevance"] > 0


@pytest.mark.parametrize(
    "script, function, args",
    [
        ("populate.py", None, []),
        ("add_new.py", "populate", []),
        ("add_new.py", "process_sitemap", ["https://example.com/sitemap.xml"]),
        ("fix_remapped_domains.py", "fix_remapped_domains", []),
    ],
)
def test_scripts_dispose_engine(monkeypatch, script, function, args):
    fake_engine = Mock()
    monkeypatch.setattr(database, "engine", fake_engine)
    monkeypatch.setattr(populate, "engine", fake_engine)
    monkeypatch.setattr(sys, "argv", [script, *args])
    monkeypatch.setenv("SITEMAPS", "")
    monkeypatch.setattr(database, "create_database", Mock())
    if function:
        monkeypatch.setattr(populate, function, Mock())
    runpy.run_path(str(ROOT / script), run_name="__main__")
    fake_engine.dispose.assert_called_once_with()


def test_cleanup_after_script_failure(monkeypatch):
    fake_engine = Mock()
    monkeypatch.setattr(populate, "engine", fake_engine)
    monkeypatch.setattr(
        populate,
        "fix_remapped_domains",
        Mock(side_effect=RuntimeError("Failed")),
    )
    with pytest.raises(RuntimeError, match="Failed"):
        runpy.run_path(str(ROOT / "fix_remapped_domains.py"), run_name="__main__")
    fake_engine.dispose.assert_called_once_with()
