"""Shared transaction guards for active agent work."""

import sqlite3
from datetime import UTC, datetime

from fastapi import HTTPException


def now() -> str:
    return datetime.now(UTC).isoformat()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise HTTPException(409, message)


def active_attempt(connection: sqlite3.Connection, run_id: str) -> sqlite3.Row:
    run = connection.execute(
        "SELECT * FROM runs WHERE run_id = ?", (run_id,)
    ).fetchone()
    if run is None:
        raise HTTPException(404, "Run not found")
    require(run["status"] == "running", "Run is no longer active")
    require(run["deadline"] is None or run["deadline"] > now(), "Attempt expired")
    if run["parent_run_id"]:
        parent = connection.execute(
            "SELECT status FROM agent_runs WHERE run_id = ?", (run["parent_run_id"],)
        ).fetchone()
        require(parent["status"] == "running", "Parent run is no longer active")
    return run
