"""A run's to-do list: one row per claim it works, tracked in SQLite."""

from typing import Any

from backend import db
from backend.errors import Conflict, NotFound

SETTLED_STATUSES = {"done", "left for a handler"}


class RunNotReady(Conflict):
    """A run can't finish while items are still being worked."""


def get_run(run_id: int) -> dict[str, Any]:
    """Return one run with its items, or raise NotFound."""
    with db.connection() as conn:
        run = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if run is None:
            raise NotFound(f"No run {run_id}")
        items = conn.execute(
            "SELECT claim_id, status, attempts, note FROM run_items "
            "WHERE run_id = ? ORDER BY claim_id",
            (run_id,),
        ).fetchall()
    return {**dict(run), "items": [dict(item) for item in items]}


def get_current_run() -> dict[str, Any]:
    """Return the most recently started run with its items, or raise NotFound."""
    with db.connection() as conn:
        row = conn.execute("SELECT MAX(run_id) AS run_id FROM runs").fetchone()
    if row["run_id"] is None:
        raise NotFound("No run yet")
    return get_run(row["run_id"])


def start_run(claim_ids: list[str]) -> dict[str, Any]:
    """Start a run with one `to do` item per claim."""
    with db.connection() as conn:
        run_id = conn.execute(
            "INSERT INTO runs (started_on) VALUES (?) RETURNING run_id", (db.now(),)
        ).fetchone()["run_id"]
        conn.executemany(
            "INSERT INTO run_items (run_id, claim_id, status) VALUES (?, ?, 'to do')",
            [(run_id, claim_id) for claim_id in claim_ids],
        )
    return get_run(run_id)


def update_run_item(
    run_id: int, claim_id: str, status: str, note: str
) -> dict[str, Any]:
    """Update one run item's status and note; `in progress` counts as an attempt."""
    with db.connection() as conn:
        updated = conn.execute(
            "UPDATE run_items SET status = ?1, note = ?2, "
            "attempts = attempts + (?1 = 'in progress') "
            "WHERE run_id = ?3 AND claim_id = ?4 "
            "RETURNING claim_id, status, attempts, note",
            (status, note, run_id, claim_id),
        ).fetchone()
    if updated is None:
        raise NotFound(f"No item for claim {claim_id} in run {run_id}")
    return dict(updated)


def finish_run(run_id: int, summary: str) -> dict[str, Any]:
    """Finish a run, recording its summary.

    Raises RunNotReady if any item isn't `done` or `left for a handler`.
    """
    outstanding = [
        item["claim_id"]
        for item in get_run(run_id)["items"]
        if item["status"] not in SETTLED_STATUSES
    ]
    if outstanding:
        raise RunNotReady(f"Still outstanding: {', '.join(outstanding)}")
    with db.connection() as conn:
        conn.execute(
            "UPDATE runs SET finished_on = ?, summary = ? WHERE run_id = ?",
            (db.now(), summary, run_id),
        )
    return get_run(run_id)
