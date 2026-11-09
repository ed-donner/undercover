"""The database: table definitions and one way to connect, on SQLite or Postgres."""

import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock

from sqlalchemy import Connection, Engine, create_engine, func, insert, select, text

from backend import money, seed_data, tables

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "undercover.db"
SCHEMA = "undercover"
CONNECTIONS_PER_PROCESS = 4


def db_path() -> Path:
    """Return the SQLite file to use, from DATABASE_PATH or the default."""
    return Path(os.environ.get("DATABASE_PATH", DEFAULT_DB_PATH))


def database_url() -> str:
    """Return the database to use: Supabase if DATABASE_URL is set, else SQLite."""
    url = os.environ.get("DATABASE_URL")
    if url:
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return f"sqlite:///{db_path()}"


_lock = Lock()
_engines: dict[str, Engine] = {}


def make_engine(url: str) -> Engine:
    """Make an engine; Postgres keeps our tables in their own schema."""
    json_options = {
        "json_serializer": lambda value: json.dumps(value, default=str),
        "json_deserializer": lambda text: money.convert(json.loads(text)),
    }
    if url.startswith("sqlite"):
        return create_engine(url, **json_options)
    return create_engine(
        url,
        **json_options,
        pool_size=CONNECTIONS_PER_PROCESS,
        max_overflow=0,
        connect_args={"options": f"-c search_path={SCHEMA}"},
    )


def engine(url: str) -> Engine:
    """Return the engine for a database, made once even when requests race for it."""
    with _lock:
        if url not in _engines:
            _engines[url] = _prepare(make_engine(url), url)
        return _engines[url]


def forget_engines() -> None:
    """Forget every engine, so the next use makes one again."""
    with _lock:
        _engines.clear()


def _prepare(made: Engine, url: str) -> Engine:
    """Create a database's schema and tables, and seed them if they are empty."""
    if not url.startswith("sqlite"):
        with made.begin() as conn:
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))
    tables.metadata.create_all(made)
    with made.begin() as conn:
        if (
            conn.execute(select(func.count()).select_from(tables.claims)).scalar_one()
            == 0
        ):
            for table, rows in seed_data.records().items():
                conn.execute(insert(table), rows)
    return made


@contextmanager
def connection() -> Iterator[Connection]:
    """Open a connection that commits on success, rolls back on error, and closes."""
    with engine(database_url()).begin() as conn:
        yield conn


def now() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(UTC).isoformat()
