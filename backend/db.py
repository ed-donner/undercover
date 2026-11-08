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
    text,
)

from backend.data import CLAIMS

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "undercover.db"
SCHEMA = "undercover"
CONNECTIONS_PER_PROCESS = 4

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
    url = os.environ.get("DATABASE_URL")
    if url:
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return f"sqlite:///{db_path()}"


def make_engine(url: str) -> Engine:
    """Make an engine; Postgres keeps our tables in their own schema."""
    if url.startswith("sqlite"):
        return create_engine(url)
    return create_engine(
        url,
        pool_size=CONNECTIONS_PER_PROCESS // 2,
        max_overflow=CONNECTIONS_PER_PROCESS // 2,
        connect_args={"options": f"-c search_path={SCHEMA}"},
    )


@lru_cache
def engine(url: str) -> Engine:
    """Make the engine for a database, creating and seeding its tables once."""
    made = make_engine(url)
    if not url.startswith("sqlite"):
        with made.begin() as conn:
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))
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
