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
from psycopg2.pool import SimpleConnectionPool


class bcolors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


def padded_enumeration(number, total):
    return f"[{str(number).rjust(len(str(total)), " ")}/{total}]"


db_connections = SimpleConnectionPool(
    1,
    10,
    host=os.environ.get("DB_HOST"),
    database=os.environ.get("DB_NAME"),
    user=os.environ.get("DB_USERNAME"),
    password=os.environ.get("DB_PASSWORD"),
    connect_timeout=3,
)


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
                f"{padded_enumeration(index + 1, self.num_urls)} [{bcolors.WARNING}SKIPPED{bcolors.ENDC}] {url} (already exists)"
            )
            return

        # Add a user-agent to avoid being blocked
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
        }
        try:
            response = requests.get(
                correct_url(url), headers=headers, timeout=10, verify=False
            )
        except Exception as e:
            print(
                f"{padded_enumeration(index + 1, self.num_urls)} [{bcolors.FAIL} ERROR {bcolors.ENDC}] {correct_url(url)} - {e}"
            )
            return

        if response.ok:
            conn = db_connections.getconn()
            with conn.cursor(
                cursor_factory=psycopg2.extras.RealDictCursor
            ) as cur:
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
                body = (
                    re.sub(r"\n+\s*", "\n", body.text).strip() if body else ""
                )

                fixed_url = correct_url(url)

                if (
                    url not in self.existing_urls
                    and fixed_url not in self.existing_urls
                ):
                    # The URL does not exist, insert it
                    query = sql.SQL("""INSERT INTO sitemap_urls (
                            title,
                            url,
                            description,
                            body
                        ) VALUES (
                            {title},
                            {url},
                            {description},
                            {body}
                        );""").format(
                        title=sql.Literal(title),
                        url=sql.Literal(fixed_url),
                        description=sql.Literal(description),
                        body=sql.Literal(body),
                    )
                    try:
                        cur.execute(query)
                        conn.commit()
                    except Exception as e:
                        print(
                            f"{padded_enumeration(index + 1, self.num_urls)} [{bcolors.FAIL} ERROR {bcolors.ENDC}] {fixed_url} - {e}"
                        )
                        db_connections.putconn(conn, close=True)
                        return

                    print(
                        f"{padded_enumeration(index + 1, self.num_urls)} [{bcolors.OKGREEN} ADDED {bcolors.ENDC}] {fixed_url}"
                    )
                    self.existing_urls.append(url)
                    self.existing_urls.append(fixed_url)
                else:
                    # The URL exists, update it
                    url_to_update = (
                        url if url in self.existing_urls else fixed_url
                    )

                    query = sql.SQL("""UPDATE sitemap_urls SET
                            url = {url},
                            title = {title},
                            description = {description},
                            body = {body},
                            date_updated = CURRENT_TIMESTAMP
                        WHERE url = {url_to_update};""").format(
                        url=sql.Literal(fixed_url),
                        title=sql.Literal(title),
                        description=sql.Literal(description),
                        body=sql.Literal(body),
                        url_to_update=sql.Literal(url_to_update),
                    )
                    try:
                        cur.execute(query)
                        conn.commit()
                    except Exception as e:
                        print(
                            f"{padded_enumeration(index + 1, self.num_urls)} [{bcolors.FAIL} ERROR {bcolors.ENDC}] {url_to_update} - {e}"
                        )
                        db_connections.putconn(conn, close=True)
                        return

                    print(
                        f"{padded_enumeration(index + 1, self.num_urls)} [{bcolors.OKBLUE}UPDATED{bcolors.ENDC}] {url_to_update} ({url})"
                    )
            db_connections.putconn(conn)
        else:
            print(
                f"{padded_enumeration(index + 1, self.num_urls)} [{bcolors.FAIL} ERROR {bcolors.ENDC}] {correct_url(url)} - {response.status_code}"
            )
            # TODO: Do we need to remove the URL from the database?
        return


def process_sitemap(sitemap, skip_existing=False):
    conn = db_connections.getconn()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT url FROM sitemap_urls;")
        existing_urls = cur.fetchall()
    db_connections.putconn(conn)
    existing_urls = [url.get("url") for url in existing_urls]

    urls = get_urls_from_sitemap(sitemap)
    engine = Engine(len(urls), existing_urls, skip_existing)
    with Pool(1) as pool:
        try:
            pool.map(
                engine, [(index, url) for index, url in enumerate(urls)], 1
            )
        except Exception as e:
            print(f"Error processing sitemap {sitemap}: {e}")
        pool.close()
        pool.join()
    print(f"Finished processing {sitemap}")


def populate(skip_existing=False, drop_table=False):
    conn = db_connections.getconn()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        if drop_table:
            cur.execute("DROP TABLE IF EXISTS sitemap_urls;")

        cur.execute("""CREATE TABLE IF NOT EXISTS sitemap_urls (
                id serial PRIMARY KEY,
                title varchar (500),
                description text,
                url varchar (500) NOT NULL,
                body text,
                date_added timestamp DEFAULT CURRENT_TIMESTAMP,
                date_updated timestamp DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(url)
            );""")
        conn.commit()
    db_connections.putconn(conn)

    sitemaps = os.getenv("SITEMAPS", "").split(",")

    for sitemap in sitemaps:
        process_sitemap(sitemap, skip_existing)


def fix_remapped_domains():
    conn = db_connections.getconn()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
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
                        sql.SQL(
                            "DELETE FROM sitemap_urls WHERE id = {id};"
                        ).format(id=sql.Literal(id))
                    )
                    print(f"Deleted existing URL: {remapped_url}")

            query = sql.SQL("""
                UPDATE sitemap_urls SET
                    url = REPLACE(url, {old_domain}, {new_domain})
                WHERE url LIKE {like_old_domain};
            """).format(
                old_domain=sql.Literal(old_domain),
                new_domain=sql.Literal(new_domain),
                like_old_domain=sql.Literal(f"%{old_domain}%"),
            )
            cur.execute(query)
            print(f"Updated URLs from {old_domain} to {new_domain}")

        conn.commit()
    db_connections.putconn(conn)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        sitemap = sys.argv[1]
        process_sitemap(sitemap=sitemap)
    else:
        populate()
    db_connections.closeall()
    exit(0)
