import ssl
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET


def parse_sitemap(sitemap_xml):
    urls = set()
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
                        urls.add(url)
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
                            urls.update(get_urls_from_sitemap(url))
    return list(urls)


def get_urls_from_sitemap(sitemap_url):
    print(f"Getting pages from {sitemap_url}...")
    root = None
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        with urllib.request.urlopen(sitemap_url, context=ctx) as f:
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
