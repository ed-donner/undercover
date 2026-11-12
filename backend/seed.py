"""Reset the database to the seeded queue: `npm run seed`.

On Postgres this drops the whole schema, the agent's saved progress included,
so stop the agent's service first.
"""

from sqlalchemy import text

from backend import db


def reset() -> None:
    """Delete every claim's state, step, run and saved progress, and seed again."""
    url = db.database_url()
    db.forget_engines()
    if url.startswith("sqlite"):
        for suffix in ("", "-wal", "-shm", "-journal"):
            db.db_path().with_name(db.db_path().name + suffix).unlink(missing_ok=True)
    else:
        with db.make_engine(url).begin() as conn:
            conn.execute(text(f"DROP SCHEMA IF EXISTS {db.SCHEMA} CASCADE"))
    db.engine(url)


if __name__ == "__main__":
    reset()
    print("Database reset to the seeded queue.")
