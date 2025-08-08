import os
import re
import sys
from multiprocessing import Pool

import psycopg2
import psycopg2.extras
import requests
from app.lib.sitemaps import get_urls_from_sitemap
from app.lib.urls import correct_url
from bs4 import BeautifulSoup
from config import DOMAIN_REMAPS
from psycopg2 import sql


def padded_enumeration(number, total):
    return f"[{str(number).rjust(len(str(total)), " ")}/{total}]"


class SingletonDB(object):
    _instance = None
    db = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(SingletonDB, cls).__new__(
                cls, *args, **kwargs
            )
        return cls._instance

    def get_connection(self):
        if not self.db:
            self.db = psycopg2.connect(
                host=os.environ.get("DB_HOST"),
                database=os.environ.get("DB_NAME"),
                user=os.environ.get("DB_USERNAME"),
                password=os.environ.get("DB_PASSWORD"),
            )
        return self.db

    def close_connection(self):
        if self.db:
            self.db.close()
            self.db = None


class Engine(object):
    def __init__(self, num_urls, existing_urls, skip_existing=False):
        self.num_urls = num_urls
        self.existing_urls = existing_urls
        self.skip_existing = skip_existing

    def __call__(self, data):
        index, url = data

        # Skip existing URLs if specified
        if self.skip_existing and url in self.existing_urls:
            print(
                f"✅ {padded_enumeration(index + 1, self.num_urls)} [SKIPPED] {url} (already exists)"
            )
            return

        # Use a user-agent to avoid being blocked
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
        }
        try:
            response = requests.get(correct_url(url), headers=headers)
        except requests.RequestException as e:
            print(
                f"⚠️ {padded_enumeration(index + 1, self.num_urls)} [ ERROR ] {url} - {e}"
            )
            return

        if response.ok:
            conn = SingletonDB().get_connection()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            soup = BeautifulSoup(response.text, "html.parser")
            title = soup.title
            title = title.text if title else None
            description = soup.find(
                "meta", attrs={"property": "og:description"}
            ) or soup.find("meta", attrs={"name": "description"})
            description = (
                description.attrs["content"]
                if description and "content" in description.attrs
                else None
            )
            body = soup.find("main") or soup.find(role="main") or soup.body
            body = re.sub(r"\n+\s*", "\n", body.text).strip() if body else ""

            fixed_url = correct_url(url)

            if (
                url not in self.existing_urls
                and fixed_url not in self.existing_urls
            ):
                # The URL does not exist, insert it
                query = sql.SQL(
                    """INSERT INTO sitemap_urls (
                        title,
                        url,
                        description,
                        body
                    ) VALUES (
                        {title},
                        {url},
                        {description},
                        {body}
                    );"""
                ).format(
                    title=sql.Literal(title),
                    url=sql.Literal(url),
                    description=sql.Literal(description),
                    body=sql.Literal(body),
                )
                cur.execute(query)

                print(
                    f"✅ {padded_enumeration(index + 1, self.num_urls)} [ ADDED ] {url}"
                )
                existing_urls = self.existing_urls + [url]
                self.existing_urls = existing_urls
            else:
                # The URL exists, update it
                url_to_update = url if url in self.existing_urls else fixed_url

                query = sql.SQL(
                    """UPDATE sitemap_urls SET
                        url = {url},
                        title = {title},
                        description = {description},
                        body = {body},
                        date_updated = CURRENT_TIMESTAMP
                    WHERE url = {url_to_update};"""
                ).format(
                    url=sql.Literal(fixed_url),
                    title=sql.Literal(title),
                    description=sql.Literal(description),
                    body=sql.Literal(body),
                    url_to_update=sql.Literal(url_to_update),
                )
                cur.execute(query)

                print(
                    f"✅ {padded_enumeration(index + 1, self.num_urls)} [UPDATED] {url}"
                )
            conn.commit()
            cur.close()
        else:
            print(
                f"⚠️ {padded_enumeration(index + 1, self.num_urls)} [ ERROR ] {url} - {response.status_code}"
            )


def process_sitemap(sitemap, skip_existing=False):
    conn = SingletonDB().get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT url FROM sitemap_urls;")
    existing_urls = cur.fetchall()
    existing_urls = [url.get("url") for url in existing_urls]
    cur.close()

    urls = get_urls_from_sitemap(sitemap)
    try:
        pool = Pool()
        engine = Engine(len(urls), existing_urls, skip_existing)
        pool.map(engine, [(index, url) for index, url in enumerate(urls)], 1)
    finally:
        pool.close()
        pool.join()
        print(f"Finished processing {sitemap}")

    SingletonDB().close_connection()


def populate(skip_existing=False, drop_table=False):
    conn = SingletonDB().get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    if drop_table:
        cur.execute("DROP TABLE IF EXISTS sitemap_urls;")

    cur.execute(
        """CREATE TABLE IF NOT EXISTS sitemap_urls (
            id serial PRIMARY KEY,
            title varchar (500),
            description text,
            url varchar (500) NOT NULL,
            body text,
            date_added timestamp DEFAULT CURRENT_TIMESTAMP,
            date_updated timestamp DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(url)
        );"""
    )
    conn.commit()
    cur.close()

    sitemaps = os.getenv("SITEMAPS", "").split(",")

    for sitemap in sitemaps:
        process_sitemap(sitemap, skip_existing)

    SingletonDB().close_connection()


def fix_remapped_domains():
    conn = SingletonDB().get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute(sql.SQL("SELECT id, url FROM sitemap_urls;"))
    all_entries = cur.fetchall()

    for old_domain, new_domain in DOMAIN_REMAPS.items():
        cur.execute(
            sql.SQL(
                "SELECT id, url FROM sitemap_urls WHERE url LIKE {old_domain};"
            ).format(old_domain=sql.Literal(f"%{old_domain}%"))
        )
        matching_old_domain_entries = cur.fetchall()
        for entry in matching_old_domain_entries:
            id = entry["id"]
            url = entry["url"]
            remapped_url = correct_url(url)

            # If the remapped domain is already in the database, delete it
            if remapped_url in [e["url"] for e in all_entries]:
                cur.execute(
                    sql.SQL("DELETE FROM sitemap_urls WHERE id = {id};").format(
                        id=sql.Literal(id)
                    )
                )
                print(f"Deleted existing URL: {remapped_url}")

        query = sql.SQL(
            """
            UPDATE sitemap_urls SET
                url = REPLACE(url, {old_domain}, {new_domain})
            WHERE url LIKE {like_old_domain};
        """
        ).format(
            old_domain=sql.Literal(old_domain),
            new_domain=sql.Literal(new_domain),
            like_old_domain=sql.Literal(f"%{old_domain}%"),
        )
        cur.execute(query)
        print(f"Updated URLs from {old_domain} to {new_domain}")

    conn.commit()
    cur.close()


if __name__ == "__main__":
    try:
        sitemap = sys.argv[1]
        process_sitemap(sitemap=sitemap)
    except IndexError:
        populate()
    exit(0)
