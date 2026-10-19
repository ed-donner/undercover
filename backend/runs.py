"""Runs of the queue agent: the to-do list, the cap and the claims it took."""

import sqlite3

from fastapi import HTTPException

from backend import claims, workflow
from backend.models import ClaimSummary, Run, Todo


def latest(db: sqlite3.Connection) -> Run | None:
    row = db.execute("SELECT * FROM runs ORDER BY run_id DESC LIMIT 1").fetchone()
    return one(db, row["run_id"]) if row else None


def one(db: sqlite3.Connection, run_id: int) -> Run:
    row = db.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Run not found")
    todos = db.execute(
        "SELECT text, status FROM todos WHERE run_id = ? ORDER BY position", (run_id,)
    ).fetchall()
    return Run(
        run_id=run_id,
        limit=row["claim_limit"],
        status=row["status"],
        summary=row["summary"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        todos=[Todo(**todo) for todo in todos],
    )


def running(db: sqlite3.Connection, run_id: int) -> Run:
    run = one(db, run_id)
    if run.status != "running":
        raise HTTPException(409, "The run has finished")
    return run


def start(db: sqlite3.Connection, limit: int) -> Run:
    if db.execute("SELECT 1 FROM runs WHERE status = 'running'").fetchone():
        raise HTTPException(409, "A run is already running")
    with db:
        cursor = db.execute(
            "INSERT INTO runs (claim_limit, status, summary, started_at)"
            " VALUES (?, 'running', '', ?)",
            (limit, workflow.now()),
        )
    return one(db, cursor.lastrowid or 0)


def write_todos(db: sqlite3.Connection, run_id: int, todos: list[Todo]) -> Run:
    one(db, run_id)
    with db:
        db.execute("DELETE FROM todos WHERE run_id = ?", (run_id,))
        db.executemany(
            "INSERT INTO todos VALUES (?, ?, ?, ?)",
            [(run_id, i, todo.text, todo.status) for i, todo in enumerate(todos)],
        )
    return one(db, run_id)


def taken(db: sqlite3.Connection, run_id: int) -> set[str]:
    rows = db.execute(
        "SELECT claim_id FROM run_claims WHERE run_id = ?", (run_id,)
    ).fetchall()
    return {row["claim_id"] for row in rows}


def take(db: sqlite3.Connection, run_id: int, claim_id: str) -> None:
    run = running(db, run_id)
    if workflow.status_of(db, claim_id) != "waiting":
        raise HTTPException(409, "The claim is not waiting")
    already = taken(db, run_id)
    if claim_id not in already and len(already) >= run.limit:
        raise HTTPException(409, f"The run's cap of {run.limit} claims is reached")
    with db:
        db.execute("INSERT OR IGNORE INTO run_claims VALUES (?, ?)", (run_id, claim_id))


def missed(db: sqlite3.Connection, run_id: int) -> list[ClaimSummary]:
    """Waiting claims the run could still take: retries first, then new ones."""
    run = one(db, run_id)
    if run.status != "running":
        return []
    already = taken(db, run_id)
    waiting = [c for c in claims.summaries(db) if c.status == "waiting"]
    retries = [c for c in waiting if c.claim_id in already]
    new = [c for c in waiting if c.claim_id not in already]
    return retries + new[: max(run.limit - len(already), 0)]


def finish(db: sqlite3.Connection, run_id: int, summary: str, status: str) -> Run:
    running(db, run_id)
    with db:
        db.execute(
            "UPDATE runs SET status = ?, summary = ?, finished_at = ? WHERE run_id = ?",
            (status, summary, workflow.now(), run_id),
        )
    return one(db, run_id)


def sweep(db: sqlite3.Connection) -> None:
    """After a restart no agent is working: close open runs and release claims."""
    with db:
        db.execute(
            "UPDATE runs SET status = 'failed', finished_at = ?"
            " WHERE status = 'running'",
            (workflow.now(),),
        )
    stuck = db.execute("SELECT claim_id FROM claims WHERE status = 'in_progress'")
    for row in stuck.fetchall():
        workflow.fail(db, row["claim_id"], "The backend restarted.")
