"""A run's to-do list: one row per claim it works, tracked in SQLite."""

from datetime import UTC, datetime
from typing import Any

from backend import db

SETTLED_STATUSES = {"done", "left for a handler"}


class RunNotReady(Exception):
    """A run can't finish while items are still being worked."""

    def __init__(self, outstanding: list[str]) -> None:
        super().__init__(f"Still outstanding: {', '.join(outstanding)}")
        self.outstanding = outstanding


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _run_dict(conn: Any, run_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    if row is None:
        return None
    items = conn.execute(
        "SELECT claim_id, status, attempts, note FROM run_items "
        "WHERE run_id = ? ORDER BY claim_id",
        (run_id,),
    ).fetchall()
    return {**dict(row), "items": [dict(item) for item in items]}


def start_run(claim_ids: list[str]) -> dict[str, Any]:
    """Start a run with one `to do` item per claim."""
    conn = db.connect()
    cursor = conn.execute("INSERT INTO runs (started_on) VALUES (?)", (_now(),))
    run_id = cursor.lastrowid
    if run_id is None:
        conn.close()
        raise RuntimeError("Could not start a run")
    conn.executemany(
        "INSERT INTO run_items (run_id, claim_id, status) VALUES (?, ?, 'to do')",
        [(run_id, claim_id) for claim_id in claim_ids],
    )
    conn.commit()
    result = _run_dict(conn, run_id)
    conn.close()
    if result is None:
        raise RuntimeError(f"Run {run_id} not found right after it was created")
    return result


def get_run(run_id: int) -> dict[str, Any] | None:
    """Return one run with its items, or None."""
    conn = db.connect()
    result = _run_dict(conn, run_id)
    conn.close()
    return result


def get_current_run() -> dict[str, Any] | None:
    """Return the most recently started run with its items, or None."""
    conn = db.connect()
    row = conn.execute(
        "SELECT run_id FROM runs ORDER BY run_id DESC LIMIT 1"
    ).fetchone()
    result = _run_dict(conn, row["run_id"]) if row else None
    conn.close()
    return result


def update_run_item(
    run_id: int, claim_id: str, status: str, note: str
) -> dict[str, Any]:
    """Update one run item's status and note.

    Moving an item to `in progress` counts as a new attempt.
    """
    conn = db.connect()
    row = conn.execute(
        "SELECT 1 FROM run_items WHERE run_id = ? AND claim_id = ?",
        (run_id, claim_id),
    ).fetchone()
    if row is None:
        conn.close()
        raise ValueError(f"No item for claim {claim_id} in run {run_id}")
    if status == "in progress":
        conn.execute(
            "UPDATE run_items SET status = ?, note = ?, attempts = attempts + 1 "
            "WHERE run_id = ? AND claim_id = ?",
            (status, note, run_id, claim_id),
        )
    else:
        conn.execute(
            "UPDATE run_items SET status = ?, note = ? "
            "WHERE run_id = ? AND claim_id = ?",
            (status, note, run_id, claim_id),
        )
    conn.commit()
    item = conn.execute(
        "SELECT claim_id, status, attempts, note FROM run_items "
        "WHERE run_id = ? AND claim_id = ?",
        (run_id, claim_id),
    ).fetchone()
    conn.close()
    return dict(item)


def finish_run(run_id: int, summary: str) -> dict[str, Any]:
    """Finish a run, recording its summary.

    Raises RunNotReady if any item isn't `done` or `left for a handler`.
    """
    conn = db.connect()
    run = _run_dict(conn, run_id)
    if run is None:
        conn.close()
        raise ValueError(f"No run {run_id}")
    outstanding = [
        item["claim_id"]
        for item in run["items"]
        if item["status"] not in SETTLED_STATUSES
    ]
    if outstanding:
        conn.close()
        raise RunNotReady(outstanding)
    conn.execute(
        "UPDATE runs SET finished_on = ?, summary = ? WHERE run_id = ?",
        (_now(), summary, run_id),
    )
    conn.commit()
    result = _run_dict(conn, run_id)
    conn.close()
    if result is None:
        raise RuntimeError(f"Run {run_id} not found right after it finished")
    return result
