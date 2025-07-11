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


def padded_enumeration(number, total):
    return f"[{str(number).rjust(len(str(total)), " ")}/{total}]"


class SingletonDB(object):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(SingletonDB, cls).__new__(
                cls, *args, **kwargs
            )
            cls._instance.db = psycopg2.connect(
                host=os.environ.get("DB_HOST"),
                database=os.environ.get("DB_NAME"),
                user=os.environ.get("DB_USERNAME"),
                password=os.environ.get("DB_PASSWORD"),
            )
        return cls._instance

    def get_connection(self):
        return self.db

    def close_connection(self):
        return self.db.close()


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

            if url not in self.existing_urls:
                # The URL does not exist, insert it
                cur.execute(
                    "INSERT INTO sitemap_urls (title, url, description, body) VALUES (%s, %s, %s, %s);",
                    (title, url, description, body),
                )
                print(
                    f"✅ {padded_enumeration(index + 1, self.num_urls)} [ ADDED ] {url}"
                )
                existing_urls = self.existing_urls + [url]
                self.existing_urls = existing_urls
            else:
                # The URL exists, update it
                cur.execute(
                    "UPDATE sitemap_urls SET title = %s, description = %s, body = %s, date_updated = CURRENT_TIMESTAMP WHERE url = %s;",
                    (title, description, body, url),
                )
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


if __name__ == "__main__":
    sitemap = sys.argv[1] or None
    if sitemap:
        process_sitemap(sitemap=sitemap)
    else:
        populate()
