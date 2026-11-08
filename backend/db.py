"""The database: table definitions and one way to connect, on SQLite or Postgres."""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from sqlalchemy import (
    Column,
    Connection,
    Engine,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    func,
    insert,
    select,
)

from backend.data import CLAIMS

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "undercover.db"

metadata = MetaData()

claims = Table(
    "claims",
    metadata,
    Column("claim_id", String, primary_key=True),
    Column("status", String, nullable=False),
    Column("thread", Integer, nullable=False, server_default="1"),
    Column("decision", String),
    Column("payout_cents", Integer),
    Column("reason", String),
    Column("policy_reference", String),
    Column("decided_on", String),
    Column("over_approval_limit", Integer),
    Column("signed_off_by", String),
    Column("signed_off_on", String),
    Column("paid_cents", Integer),
    Column("paid_on", String),
)

claim_steps = Table(
    "claim_steps",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("claim_id", String, nullable=False),
    Column("recorded_on", String, nullable=False),
    Column("text", String, nullable=False),
)

runs = Table(
    "runs",
    metadata,
    Column("run_id", Integer, primary_key=True, autoincrement=True),
    Column("started_on", String, nullable=False),
    Column("finished_on", String),
    Column("summary", String),
)

run_items = Table(
    "run_items",
    metadata,
    Column("run_id", Integer, primary_key=True),
    Column("claim_id", String, primary_key=True),
    Column("status", String, nullable=False),
    Column("attempts", Integer, nullable=False, server_default="0"),
    Column("note", String),
)


def db_path() -> Path:
    """Return the SQLite file to use, from DATABASE_PATH or the default."""
    return Path(os.environ.get("DATABASE_PATH", DEFAULT_DB_PATH))


def database_url() -> str:
    """Return the database to use: Supabase if DATABASE_URL is set, else SQLite."""
    return f"sqlite:///{db_path()}"


@lru_cache
def engine(url: str) -> Engine:
    """Make the engine for a database, creating and seeding its tables once."""
    made = create_engine(url)
    metadata.create_all(made)
    with made.begin() as conn:
        if conn.execute(select(func.count()).select_from(claims)).scalar_one() == 0:
            conn.execute(
                insert(claims),
                [{"claim_id": claim_id, "status": "waiting"} for claim_id in CLAIMS],
            )
    return made


@contextmanager
def connection() -> Iterator[Connection]:
    """Open a connection that commits on success, rolls back on error, and closes."""
    with engine(database_url()).begin() as conn:
        yield conn


def now() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(UTC).isoformat()
