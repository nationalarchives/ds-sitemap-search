import os
import re
import sys
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, load_only

from app.lib.database import create_database, engine
from app.lib.sitemaps import get_urls_from_sitemap
from app.lib.urls import correct_url
from app.models import SitemapURL

MAX_REQUEST_ATTEMPTS = int(os.getenv("MAX_REQUEST_ATTEMPTS", "3"))
RETRY_DELAY_SECONDS = int(os.getenv("RETRY_DELAY_SECONDS", "10"))


def padded_enumeration(number, total):
    return f"[{str(number).rjust(len(str(total)), ' ')}/{total}]"


class PageIndexer:
    def __init__(
        self,
        http,
        num_urls,
        existing_urls,
        skip_existing=False,
        delete_redirects_to_existing_urls=False,
    ):
        self.http = http
        self.http.headers.update({"User-Agent": "ds-sitemap-search"})
        if UNRESTRICTED_ACCESS_HEADER := os.getenv("UNRESTRICTED_ACCESS_HEADER"):
            self.http.headers.update(
                {"x-external-access-key": UNRESTRICTED_ACCESS_HEADER}
            )
        self.num_urls = num_urls
        self.existing_urls = existing_urls
        self.skip_existing = skip_existing
        self.delete_redirects_to_existing_urls = delete_redirects_to_existing_urls

    def __call__(self, data):
        index, url = data
        fixed_url = correct_url(url)
        progress = padded_enumeration(index + 1, self.num_urls)
        if self.skip_existing and (
            url in self.existing_urls or fixed_url in self.existing_urls
        ):
            print(f"{progress} [SKIPPED] {url} (already exists)")
            return

        response = self._get_response(fixed_url, progress)
        if response is None:
            return

        with response:
            if self._handle_redirect(response, url, fixed_url, progress):
                return
            values = self._response_values(response)
            added = self._store_response(url, fixed_url, values)

        self.existing_urls.update((url, fixed_url))
        if response.status_code in [200, 404, 410]:
            action = " ADDED " if added else "UPDATED"
            print(f"{progress} [{action} ({response.status_code})] {fixed_url}")
        else:
            print(f"{progress} [ERROR] {fixed_url} - {response.status_code}")

    def _get_response(self, fixed_url, progress):
        for attempt in range(MAX_REQUEST_ATTEMPTS):
            try:
                response = self.http.get(
                    fixed_url,
                    timeout=10,
                    headers=self.http.headers,
                )
            except requests.RequestException as error:
                print(f"{progress} [ ERROR ] {fixed_url} - {error}")
                return None
            if response.status_code < 500 or attempt == MAX_REQUEST_ATTEMPTS - 1:
                return response
            response.close()
            time.sleep(RETRY_DELAY_SECONDS)

        return None

    @staticmethod
    def _redirect_targets(response, fixed_url):
        targets = set()
        for redirect in response.history:
            location = redirect.headers.get("Location")
            if location:
                destination = urljoin(redirect.url or fixed_url, location)
                targets.update((destination, correct_url(destination)))
        if 300 <= response.status_code < 400:
            location = response.headers.get("Location")
            if location:
                destination = urljoin(fixed_url, location)
                targets.update((destination, correct_url(destination)))
        if response.history and response.url:
            targets.update((response.url, correct_url(response.url)))
        return targets

    def _handle_redirect(self, response, url, fixed_url, progress):
        if not self.delete_redirects_to_existing_urls or not (
            response.history or 300 <= response.status_code < 400
        ):
            return False

        redirect_targets = self._redirect_targets(response, fixed_url)
        if response.history and 400 <= response.status_code < 500:
            self._update_redirected_error(response, url, fixed_url, progress)
            return True

        existing_targets = (redirect_targets & self.existing_urls) - {url, fixed_url}
        if not existing_targets:
            return False

        redirect_url = next(iter(existing_targets))
        with Session(engine) as session, session.begin():
            entries = session.scalars(
                select(SitemapURL).where(SitemapURL.url.in_({url, fixed_url}))
            ).all()
            for entry in entries:
                session.delete(entry)
        self.existing_urls.difference_update((url, fixed_url))
        print(f"{progress} [DELETED] {url} (redirects to existing URL: {redirect_url})")
        return True

    def _update_redirected_error(self, response, url, fixed_url, progress):
        final_url = response.url or fixed_url
        destination = correct_url(final_url)
        with Session(engine) as session, session.begin():
            entries = {
                entry.url: entry
                for entry in session.scalars(
                    select(SitemapURL).where(
                        SitemapURL.url.in_({url, fixed_url, final_url, destination})
                    )
                )
            }
            entry = (
                entries.get(destination)
                or entries.get(final_url)
                or entries.get(fixed_url)
                or entries.get(url)
            )
            if entry is None:
                entry = SitemapURL(url=destination)
                session.add(entry)
            for duplicate in entries.values():
                if duplicate is not entry:
                    session.delete(duplicate)
            entry.url = destination
            entry.response_code = response.status_code
            entry.date_updated = func.current_timestamp()
        self.existing_urls.difference_update((url, fixed_url, final_url))
        self.existing_urls.add(destination)
        print(f"{progress} [UPDATED ({response.status_code})] {destination}")

    @staticmethod
    def _response_values(response):
        response_code = response.status_code
        if not (200 <= response_code < 300 or 400 <= response_code < 600):
            response_code = None
        values = {"response_code": response_code}
        if 200 <= response.status_code < 300:
            soup = BeautifulSoup(response.text, "html.parser")
            description = soup.find(
                "meta", attrs={"property": "og:description"}
            ) or soup.find("meta", attrs={"name": "description"})
            body = soup.find("main") or soup.find(role="main") or soup.body
            values.update(
                title=soup.title.text if soup.title else None,
                description=(description.get("content") if description else None),
                body=(re.sub(r"\n+\s*", "\n", body.text).strip() if body else ""),
            )
        return values

    @staticmethod
    def _store_response(url, fixed_url, values):
        with Session(engine) as session, session.begin():
            entries = {
                entry.url: entry
                for entry in session.scalars(
                    select(SitemapURL)
                    .options(load_only(SitemapURL.id, SitemapURL.url))
                    .where(SitemapURL.url.in_({url, fixed_url}))
                )
            }
            entry = entries.get(fixed_url) or entries.get(url)
            added = entry is None
            if added:
                entry = SitemapURL(url=fixed_url)
                session.add(entry)
            elif url != fixed_url and len(entries) > 1:
                session.delete(entries[url])
            entry.url = fixed_url
            for field, value in values.items():
                setattr(entry, field, value)
            entry.date_updated = func.current_timestamp()
        return added


def process_sitemap(sitemap, skip_existing=False):
    create_database()
    existing_urls = set()
    if skip_existing:
        with Session(engine) as session:
            existing_urls.update(session.scalars(select(SitemapURL.url)))

    urls = get_urls_from_sitemap(sitemap)
    with requests.Session() as http:
        http.headers.update({"User-Agent": "ds-sitemap-search"})
        if UNRESTRICTED_ACCESS_HEADER := os.getenv("UNRESTRICTED_ACCESS_HEADER"):
            http.headers.update({"x-external-access-key": UNRESTRICTED_ACCESS_HEADER})
        indexer = PageIndexer(http, len(urls), existing_urls, skip_existing)
        for data in enumerate(urls):
            indexer(data)
    print(f"Finished processing {sitemap}")
    return urls


def populate(skip_existing=False, drop_table=False):
    create_database(drop_table=drop_table)
    sitemap_urls = set()
    for sitemap in filter(None, os.getenv("SITEMAPS", "").split(",")):
        sitemap_urls.update(process_sitemap(sitemap, skip_existing))
    reindex_orphaned_urls(sitemap_urls)


def reindex_orphaned_urls(sitemap_urls):
    sitemap_urls.update({correct_url(url) for url in sitemap_urls})
    with Session(engine) as session:
        rows = session.execute(select(SitemapURL.url, SitemapURL.response_code)).all()
    existing_urls = {url for url, _ in rows}
    urls_to_retest = [
        url
        for url, response_code in rows
        if response_code is not None
        and 200 <= response_code < 300
        and url not in sitemap_urls
        and correct_url(url) not in sitemap_urls
    ]

    with requests.Session() as http:
        indexer = PageIndexer(
            http,
            len(urls_to_retest),
            existing_urls,
            delete_redirects_to_existing_urls=True,
        )
        for data in enumerate(urls_to_retest):
            indexer(data)


def fix_remapped_domains():
    create_database()
    with Session(engine) as session, session.begin():
        entries = {
            entry.url: entry
            for entry in session.scalars(
                select(SitemapURL).options(load_only(SitemapURL.id, SitemapURL.url))
            )
        }
        for url, entry in list(entries.items()):
            remapped_url = correct_url(url)
            if url == remapped_url:
                continue
            if remapped_url in entries:
                session.delete(entry)
                print(f"Deleted duplicate URL: {url}")
            else:
                entry.url = remapped_url
                entries[remapped_url] = entry
                print(f"Updated URL: {url} -> {remapped_url}")
            del entries[url]


def reindex_errors():
    create_database()
    with Session(engine) as session, session.begin():
        existing_urls = set(session.scalars(select(SitemapURL.url)).all())
        session.execute(
            update(SitemapURL)
            .where(
                (SitemapURL.response_code < 200)
                | ((SitemapURL.response_code >= 300) & (SitemapURL.response_code < 400))
                | (SitemapURL.response_code >= 600)
            )
            .values(response_code=None)
        )
        urls_to_reindex = session.scalars(
            select(SitemapURL.url).where(
                (SitemapURL.response_code >= 300)
                | (SitemapURL.response_code < 200)
                | (SitemapURL.response_code == None)
            )
        ).all()
    http = requests.Session()
    indexer = PageIndexer(
        http,
        len(urls_to_reindex),
        existing_urls,
        skip_existing=False,
        delete_redirects_to_existing_urls=True,
    )
    for data in enumerate(urls_to_reindex):
        indexer(data)


if __name__ == "__main__":
    try:
        if len(sys.argv) > 1:
            process_sitemap(sitemap=sys.argv[1])
        else:
            populate()
    finally:
        engine.dispose()
