import os
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from multiprocessing import Pool

import psycopg2
import psycopg2.extras
import requests
from bs4 import BeautifulSoup


def parse_sitemap(sitemap_xml):
    urls = []
    if sitemap_xml is not None and (
        sitemap_xml.tag == "{http://www.sitemaps.org/schemas/sitemap/0.9}urlset"
    ):
        for url in sitemap_xml:
            if url.tag == "{http://www.sitemaps.org/schemas/sitemap/0.9}url":
                for loc in url:
                    if (
                        loc.tag
                        == "{http://www.sitemaps.org/schemas/sitemap/0.9}loc"
                    ):
                        url = loc.text
                        urls.append(url)
    elif sitemap_xml is not None and (
        sitemap_xml.tag
        == "{http://www.sitemaps.org/schemas/sitemap/0.9}sitemapindex"
    ):
        for sitemap in sitemap_xml:
            if (
                sitemap.tag
                == "{http://www.sitemaps.org/schemas/sitemap/0.9}sitemap"
            ):
                for loc in sitemap:
                    if (
                        loc.tag
                        == "{http://www.sitemaps.org/schemas/sitemap/0.9}loc"
                    ):
                        url = loc.text
                        if " " not in url:
                            urls = urls + get_urls_from_sitemap(url)
    return urls


def get_urls_from_sitemap(sitemap_url):
    print(f"Getting pages from {sitemap_url}...")
    root = None
    try:
        with urllib.request.urlopen(sitemap_url) as f:
            xml = f.read().decode("utf-8")
            root = ET.fromstring(xml)
            return parse_sitemap(root)
    except urllib.error.HTTPError as e:
        print(f"⚠️ [ FAIL ] {sitemap_url} - HTTPError: {e.code}")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"⚠️ [ FAIL ] {sitemap_url} - URLError: {e.reason}")
        sys.exit(1)
    print(f"⚠️ [ FAIL ] {sitemap_url} - An unknown error occured")
    sys.exit(1)


def padded_enumeration(number, total):
    return f"[{str(number).rjust(len(str(total)), " ")}/{total}]"


def get_db_conn():
    return psycopg2.connect(
        host=os.environ.get("DB_HOST"),
        database=os.environ.get("DB_NAME"),
        user=os.environ.get("DB_USERNAME"),
        password=os.environ.get("DB_PASSWORD"),
    )


class Engine(object):
    def __init__(self, num_urls, existing_urls):
        self.num_urls = num_urls
        self.existing_urls = existing_urls

    def __call__(self, data):
        index, url = data
        conn = get_db_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        response = requests.get(url)
        if response.ok:
            html = response.text
            soup = BeautifulSoup(html, "lxml")
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
                self.existing_urls.append(url)
                cur.execute(
                    "INSERT INTO sitemap_urls (title, url, description, body) VALUES (%s, %s, %s, %s);",
                    (title, url, description, body),
                )
                print(
                    f"✅ {padded_enumeration(index + 1, self.num_urls)} [ ADDED ] {url}"
                )
            else:
                cur.execute(
                    "UPDATE sitemap_urls SET title = %s, description = %s, body = %s WHERE url = %s;",
                    (title, description, body, url),
                )
                print(
                    f"✅ {padded_enumeration(index + 1, self.num_urls)} [UPDATED] {url}"
                )
            conn.commit()
        else:
            print(
                f"⚠️ {padded_enumeration(index + 1, self.num_urls)} [ ERROR ] {url} - {response.status_code}"
            )
        cur.close()
        conn.close()


def populate():
    conn = get_db_conn()

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    # cur.execute("DROP TABLE IF EXISTS sitemap_urls;")  # Uncomment to drop the table
    cur.execute(
        """CREATE TABLE IF NOT EXISTS sitemap_urls (
            id serial PRIMARY KEY,
            title varchar (500),
            description text,
            url varchar (500) NOT NULL,
            body text,
            date_added timestamp DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(url)
        );"""
    )
    conn.commit()

    cur.execute("SELECT url FROM sitemap_urls;")
    existing_urls = cur.fetchall()
    cur.close()
    conn.close()

    existing_urls = [result["url"] for result in existing_urls]

    sitemaps = os.getenv("SITEMAPS", "").split(",")

    for sitemap in sitemaps:
        urls = get_urls_from_sitemap(sitemap)
        try:
            pool = Pool()
            engine = Engine(len(urls), existing_urls)
            pool.map(engine, [(index, url) for index, url in enumerate(urls)], 1)
        finally:
            pool.close()
            pool.join()
            print(f"Finished processing {sitemap}")


if __name__ == "__main__":
    populate()
