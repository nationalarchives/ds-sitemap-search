from populate import engine, fix_remapped_domains

if __name__ == "__main__":
    try:
        fix_remapped_domains()
    finally:
        engine.dispose()
