import sys

from populate import db_connections, fix_remapped_domains

if __name__ == "__main__":
    fix_remapped_domains()
    db_connections.closeall()
    sys.exit(0)
