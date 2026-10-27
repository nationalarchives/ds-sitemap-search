import importlib.util
import runpy
import sys
import threading
from pathlib import Path
from unittest.mock import Mock, create_autospec

import pytest
from psycopg_pool import ConnectionPool


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def population(monkeypatch):
    pool_factory = create_autospec(ConnectionPool)
    monkeypatch.setattr("psycopg_pool.ConnectionPool", pool_factory)
    spec = importlib.util.spec_from_file_location(
        "population_under_test", ROOT / "populate.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, pool_factory


def test_pool_configuration(population):
    module, pool_factory = population
    pool_factory.assert_called_once()
    options = pool_factory.call_args.kwargs
    assert options["min_size"] == 1
    assert options["max_size"] == 10
    assert options["kwargs"]["connect_timeout"] == 3
    assert set(options["kwargs"]) == {
        "host",
        "dbname",
        "user",
        "password",
        "connect_timeout",
    }
    assert module.db_connections is pool_factory.return_value


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("fails", [False, True])
def test_engine_returns_connections(population, monkeypatch, existing, fails):
    module, _ = population
    url = "https://example.com/page"
    monkeypatch.setattr(module, "correct_url", lambda value: value)
    monkeypatch.setattr(
        module.requests,
        "get",
        Mock(
            return_value=Mock(
                ok=True, text="<title>Page</title><main>Body</main>"
            )
        ),
    )
    connection = module.db_connections.getconn.return_value
    cursor = connection.cursor.return_value.__enter__.return_value
    if fails:
        cursor.execute.side_effect = RuntimeError("Database failure")

    module.Engine(1, [url] if existing else [])((0, url))

    cursor.execute.assert_called_once()
    module.db_connections.putconn.assert_called_once_with(connection)
    if fails:
        connection.close.assert_called_once_with()
        connection.commit.assert_not_called()
    else:
        connection.close.assert_not_called()
        connection.commit.assert_called_once_with()


def test_sitemap_worker_shares_pool_in_same_process(population, monkeypatch):
    module, _ = population
    cursor = (
        module.db_connections.getconn.return_value
        .cursor.return_value.__enter__.return_value
    )
    cursor.fetchall.return_value = []
    urls = ["https://example.com/one", "https://example.com/two"]
    monkeypatch.setattr(module, "get_urls_from_sitemap", Mock(return_value=urls))
    calls = []

    def process(data):
        calls.append((data, threading.get_ident()))
        module.db_connections.getconn()

    monkeypatch.setattr(module, "Engine", Mock(return_value=process))
    module.process_sitemap("https://example.com/sitemap.xml")

    assert [data for data, _ in calls] == list(enumerate(urls))
    assert len({worker_id for _, worker_id in calls}) == 1
    assert calls[0][1] != threading.get_ident()
    assert module.db_connections.getconn.call_count == 3


@pytest.mark.parametrize("script", ["add_new.py", "fix_remapped_domains.py"])
def test_script_closes_pool(population, monkeypatch, script):
    module, _ = population
    monkeypatch.setitem(sys.modules, "populate", module)
    monkeypatch.setattr(sys, "argv", [script])
    monkeypatch.setattr(module, "populate", Mock())
    monkeypatch.setattr(module, "fix_remapped_domains", Mock())

    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(str(ROOT / script), run_name="__main__")

    assert exit_info.value.code == 0
    module.db_connections.close.assert_called_once_with()


def test_population_script_closes_pool(population, monkeypatch):
    module, _ = population
    cursor = (
        module.db_connections.getconn.return_value
        .cursor.return_value.__enter__.return_value
    )
    cursor.fetchall.return_value = []
    monkeypatch.setattr(sys, "argv", ["populate.py"])
    monkeypatch.setenv("SITEMAPS", "https://example.com/sitemap.xml")
    monkeypatch.setattr(
        "app.lib.sitemaps.get_urls_from_sitemap", Mock(return_value=[])
    )

    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(str(ROOT / "populate.py"), run_name="__main__")

    assert exit_info.value.code == 0
    module.db_connections.close.assert_called_once_with()
