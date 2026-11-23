"""Reset the database to the seed data: uv run -m backend.reset."""

from backend.db import SCHEMA, session
from backend.seed import init_db


def reset():
    """Drop every table and load the seed data again."""
    with session() as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master"
            " WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        for (name,) in tables:
            conn.execute(f"DROP TABLE {name}")  # noqa: S608
        conn.executescript(SCHEMA)
    init_db()


if __name__ == "__main__":
    reset()
