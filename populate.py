import os
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

import psycopg2
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
                        url = re.sub(
                            "http://website.live.local",
                            "https://www.nationalarchives.gov.uk",
                            url,
                        )
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
                        url = re.sub(
                            "http://website.live.local",
                            "https://www.nationalarchives.gov.uk",
                            url,
                        )
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


def populate():
    conn = psycopg2.connect(
        host=os.environ.get("DB_HOST"),
        database=os.environ.get("DB_NAME"),
        user=os.environ.get("DB_USERNAME"),
        password=os.environ.get("DB_PASSWORD"),
    )
    cur = conn.cursor()
    # cur.execute("DROP TABLE IF EXISTS sitemap_urls;")
    cur.execute(
        """CREATE TABLE IF NOT EXISTS sitemap_urls (
            id serial PRIMARY KEY,
            title varchar (500),
            description text,
            url varchar (500) NOT NULL,
            body text,
            date_added timestamp DEFAULT CURRENT_TIMESTAMP
        );"""
    )
    conn.commit()
    sitemaps = os.getenv("SITEMAPS", "").split(",")
    for sitemap in sitemaps:
        urls = get_urls_from_sitemap(sitemap)
        urls_checked = []
        for index, url in enumerate(urls):
            if url not in urls_checked:
                html = requests.get(url).text
                soup = BeautifulSoup(html, "lxml")
                title = soup.title
                title = (
                    re.sub(r" - The National Archives$", "", title.text)
                    if title
                    else None
                )
                description = soup.find(
                    "meta", attrs={"property": "og:description"}
                ) or soup.find("meta", attrs={"name": "description"})
                description = (
                    description.attrs["content"]
                    if description and "content" in description.attrs
                    else None
                )
                body = soup.find("main") or soup.find(role="main") or soup.body
                body = (
                    re.sub(r"\n+\s*", "\n", body.text).strip() if body else ""
                )
                print(
                    f"[{str(index + 1).rjust(len(str(len(urls))), " ")}/{len(urls)}] {url}"
                )
                urls_checked.append(url)
                cur.execute(
                    "INSERT INTO sitemap_urls (title, url, description, body) VALUES (%s, %s, %s, %s);",
                    (title, url, description, body),
                )
                conn.commit()
    cur.close()
    conn.close()


if __name__ == "__main__":
    populate()
