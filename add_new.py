import sys

from populate import engine, populate, process_sitemap

if __name__ == "__main__":
    try:
        if len(sys.argv) > 1:
            process_sitemap(sitemap=sys.argv[1], skip_existing=True)
        else:
            populate(skip_existing=True)
    finally:
        engine.dispose()
