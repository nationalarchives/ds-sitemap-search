import sys

from populate import db_connections, populate, process_sitemap

if __name__ == "__main__":
    if len(sys.argv) > 1:
        sitemap = sys.argv[1]
        process_sitemap(sitemap=sitemap, skip_existing=True)
    else:
        populate(skip_existing=True)
    db_connections.closeall()
    exit(0)
