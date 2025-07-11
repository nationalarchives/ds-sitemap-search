import sys

from populate import populate, process_sitemap

if __name__ == "__main__":
    try:
        sitemap = sys.argv[1]
        process_sitemap(sitemap=sitemap, skip_existing=True)
        exit(0)
    except IndexError:
        populate(skip_existing=True)
