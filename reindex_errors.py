from populate import engine, reindex_errors

if __name__ == "__main__":
    try:
        reindex_errors()
    finally:
        engine.dispose()
