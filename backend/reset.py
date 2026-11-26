"""Rebuild the database from data/: uv run -m backend.reset"""

from backend.db import db_path, seed

if __name__ == "__main__":
    seed(db_path())
    print(f"Rebuilt {db_path()}")
