import sys

from populate import populate, process_sitemap

if __name__ == "__main__":
    sitemap = sys.argv[1] or None
    if sitemap:
        process_sitemap(sitemap=sitemap, skip_existing=True)
    else:
        populate(skip_existing=True)
