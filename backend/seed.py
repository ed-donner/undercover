"""Rebuild the Shoppie database from the source records."""

from backend.main import database_path
from backend.store import Store

if __name__ == "__main__":
    Store(database_path()).reseed()
    print(f"Seeded {database_path()}")
