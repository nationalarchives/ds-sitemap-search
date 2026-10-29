import os
import re
import sys

import requests
from bs4 import BeautifulSoup
from sqlalchemy import func, select
from sqlalchemy.orm import Session, load_only

from app.lib.database import create_database, engine
from app.lib.sitemaps import get_urls_from_sitemap
from app.lib.urls import correct_url
from app.models import SitemapURL


def padded_enumeration(number, total):
    return f"[{str(number).rjust(len(str(total)), ' ')}/{total}]"


class PageIndexer:
    def __init__(self, http, num_urls, existing_urls, skip_existing=False):
        self.http = http
        self.http.headers.update({"User-Agent": "ds-sitemap-search"})
        if UNRESTRICTED_ACCESS_HEADER := os.getenv("UNRESTRICTED_ACCESS_HEADER"):
            self.http.headers.update(
                {"x-external-access-key": UNRESTRICTED_ACCESS_HEADER}
            )
        self.num_urls = num_urls
        self.existing_urls = existing_urls
        self.skip_existing = skip_existing

    def __call__(self, data):
        index, url = data
        fixed_url = correct_url(url)
        progress = padded_enumeration(index + 1, self.num_urls)
        if self.skip_existing and (
            url in self.existing_urls or fixed_url in self.existing_urls
        ):
            print(f"{progress} [SKIPPED] {url} (already exists)")
            return

        try:
            response = self.http.get(fixed_url, timeout=10, headers=self.http.headers)
        except requests.RequestException as error:
            print(f"{progress} [ ERROR ] {fixed_url} - {error}")
            return

        with response:
            values = {"response_code": response.status_code}
            if response.ok:
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

            self.existing_urls.update((url, fixed_url))
            if response.status_code in [200, 404, 410]:
                action = " ADDED " if added else "UPDATED"
                print(f"{progress} [{action} ({response.status_code})] {fixed_url}")
            else:
                print(f"{progress} [ERROR] {fixed_url} - {response.status_code}")


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


def populate(skip_existing=False, drop_table=False):
    create_database(drop_table=drop_table)
    for sitemap in filter(None, os.getenv("SITEMAPS", "").split(",")):
        process_sitemap(sitemap, skip_existing)


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
    urls_to_reindex = []
    with Session(engine) as session:
        urls_to_reindex = session.scalars(
            select(SitemapURL.url).where(
                (SitemapURL.response_code >= 400) | (SitemapURL.response_code == None)
            )
        ).all()
    http = requests.Session()
    indexer = PageIndexer(
        http, len(urls_to_reindex), set(urls_to_reindex), skip_existing=False
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
