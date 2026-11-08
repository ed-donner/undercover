"""Rebuild the Shoppie database from the source records."""

from dotenv import load_dotenv

from backend.store import SCHEMA, Store


def seed_database() -> str:
    """Reseed the configured Postgres or SQLite database and return a status line."""
    load_dotenv(override=True)
    store = Store()
    store.reseed()
    target = f"Postgres schema '{SCHEMA}'" if store.is_postgres else store.database_path
    return f"Seeded {target}"


if __name__ == "__main__":
    print(seed_database())
