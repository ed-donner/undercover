"""The agent's saved progress: the one module that talks to Postgres.

LangGraph saves a claim's state here after every step, in the same Supabase
database as the backend, in the `undercover` schema.
"""

import os
from functools import lru_cache

from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

SCHEMA = "undercover"
CONNECTIONS_PER_PROCESS = 2


@lru_cache
def saver() -> PostgresSaver:
    """Return this process's checkpointer, with its tables ready."""
    pool = ConnectionPool(
        os.environ["DATABASE_URL"],
        max_size=CONNECTIONS_PER_PROCESS,
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
            "options": f"-c search_path={SCHEMA}",
        },
        open=False,
    )
    pool.open()
    with pool.connection() as connection:
        connection.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
    checkpointer = PostgresSaver(pool)  # pyright: ignore[reportArgumentType]
    checkpointer.setup()
    return checkpointer
