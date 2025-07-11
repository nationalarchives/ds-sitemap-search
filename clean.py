from populate import populate

if __name__ == "__main__":
    if (
        input(
            "Are you sure you want to drop all URLs? This cannot be undone. Type 'yes' to confirm: "
        )
        == "yes"
    ):
        print("Dropping all URLs and re-indexing...")
        populate(drop_table=True)
    else:
        print("Operation cancelled. No URLs were dropped.")
