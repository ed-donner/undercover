"""The agent's saved progress: the one module that talks to Postgres.

LangGraph saves a claim's state here after every step, in the same Supabase
database as the backend, in the `undercover` schema.
"""

import os
from functools import lru_cache
from threading import Lock

from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

SCHEMA = "undercover"
CONNECTIONS_PER_PROCESS = 2


_creating = Lock()


def saver() -> PostgresSaver:
    """Return this process's checkpointer, made once even when claims race for it.

    Claims are worked in parallel threads, and each racing thread would
    otherwise open a pool of its own, using up the database's connections.
    """
    with _creating:
        return _make_saver()


@lru_cache
def _make_saver() -> PostgresSaver:
    pool = ConnectionPool(
        os.environ["DATABASE_URL"],
        min_size=CONNECTIONS_PER_PROCESS,
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
