"""Runs of the agent: the cap, the to-do list and the claims each run works."""

import json
import sqlite3
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.db import claim_row, connect, now, set_todo_state, sweep_stuck

router = APIRouter()
NO_CAP = 1000


class Todo(BaseModel):
    """One item of the agent's to-do list."""

    text: str = Field(min_length=1)
    state: Literal["todo", "in_progress", "done", "left_for_handler"]
    claim_id: str


class Todos(BaseModel):
    """The agent's whole to-do list."""

    items: list[Todo]


class NewRun(BaseModel):
    """A run on the queue, capped at a number of claims."""

    cap: int = Field(gt=0)


class NewClaimRun(BaseModel):
    """A run on one named claim."""

    claim_id: str


class Finish(BaseModel):
    """The summary a run ends with."""

    summary: str


def run_row(conn: sqlite3.Connection, run_id: int) -> sqlite3.Row:
    """Return a run row or answer 404."""
    row = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
    if row is None:
        raise HTTPException(404, f"No run {run_id}")
    return row


def worked(conn: sqlite3.Connection, run_id: int) -> list[str]:
    """Return the claims a run has started, in order."""
    rows = conn.execute(
        "SELECT claim_id FROM run_claims WHERE run_id=? ORDER BY rowid", (run_id,)
    )
    return [r["claim_id"] for r in rows]


def waiting(conn: sqlite3.Connection, run: sqlite3.Row) -> list[sqlite3.Row]:
    """Return the waiting claims the run may work."""
    rows = conn.execute(
        "SELECT claim_id, data FROM claims WHERE status='waiting' ORDER BY claim_id"
    ).fetchall()
    return [r for r in rows if not run["claim_id"] or r["claim_id"] == run["claim_id"]]


def begin(conn: sqlite3.Connection, cap: int, claim_id: str) -> dict[str, int]:
    """Start a run after clearing any claim stuck in progress."""
    sweep_stuck(conn)
    conn.execute("UPDATE runs SET status='abandoned' WHERE status='running'")
    cursor = conn.execute(
        "INSERT INTO runs (cap, claim_id, started_at) VALUES (?, ?, ?)",
        (cap, claim_id, now()),
    )
    return {"run_id": cursor.lastrowid or 0, "cap": cap}


@router.post("/api/runs", operation_id="start_run")
def start_run(run: NewRun) -> dict[str, int]:
    """Start a run on the queue, capped at a number of claims."""
    with connect() as conn:
        return begin(conn, run.cap, "")


@router.post("/api/runs/claim", operation_id="start_claim_run")
def start_claim_run(run: NewClaimRun) -> dict[str, int]:
    """Start a run on one named claim."""
    with connect() as conn:
        claim_row(conn, run.claim_id)
        return begin(conn, 1, run.claim_id)


@router.get("/api/runs/current", operation_id="get_current_run")
def get_current_run() -> dict[str, Any] | None:
    """Return the latest run with its to-do list, or null if there was none."""
    with connect() as conn:
        run = conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 1").fetchone()
        if run is None:
            return None
        items = conn.execute(
            "SELECT text, state, claim_id FROM todos WHERE run_id=? ORDER BY id",
            (run["id"],),
        ).fetchall()
        return {
            "run_id": run["id"],
            "cap": run["cap"],
            "claim_id": run["claim_id"],
            "status": run["status"],
            "summary": run["summary"],
            "started_at": run["started_at"],
            "claims": worked(conn, run["id"]),
            "todos": [dict(i) for i in items],
        }


@router.put("/api/runs/{run_id}/todos", operation_id="write_todos")
def write_todos(run_id: int, todos: Todos) -> dict[str, int]:
    """Replace the run's to-do list."""
    with connect() as conn:
        run_row(conn, run_id)
        conn.execute("DELETE FROM todos WHERE run_id=?", (run_id,))
        conn.executemany(
            "INSERT INTO todos (run_id, text, state, claim_id) VALUES (?, ?, ?, ?)",
            [(run_id, t.text, t.state, t.claim_id) for t in todos.items],
        )
    return {"items": len(todos.items)}


@router.get("/api/runs/{run_id}/waiting", operation_id="list_waiting_claims")
def list_waiting_claims(run_id: int) -> dict[str, Any]:
    """List the waiting claims a run may work, with its cap and claims worked."""
    with connect() as conn:
        run = run_row(conn, run_id)
        claims = []
        for row in waiting(conn, run):
            data = json.loads(row["data"])
            claims.append(
                {
                    "claim_id": row["claim_id"],
                    "claim_type": data["claim_type"],
                    "summary": data["summary"],
                    "amount_claimed": data["amount_claimed"],
                }
            )
        return {
            "cap": run["cap"],
            "worked": worked(conn, run_id),
            "waiting": claims,
        }


@router.get("/api/runs/{run_id}/missed", operation_id="check_missed_claims")
def check_missed_claims(run_id: int) -> dict[str, list[str]]:
    """List the waiting claims within the run's cap that it has not finished."""
    with connect() as conn:
        run = run_row(conn, run_id)
        done = worked(conn, run_id)
        ids = [r["claim_id"] for r in waiting(conn, run)]
        retries = [c for c in ids if c in done]
        fresh = [c for c in ids if c not in done][: max(run["cap"] - len(done), 0)]
    return {"missed": retries + fresh}


@router.post("/api/runs/{run_id}/claims/{claim_id}/start", operation_id="start_claim")
def start_claim(run_id: int, claim_id: str) -> dict[str, int]:
    """Start work on a waiting claim, within the run's cap."""
    with connect() as conn:
        run = run_row(conn, run_id)
        claim = claim_row(conn, claim_id)
        done = worked(conn, run_id)
        if run["status"] != "running":
            raise HTTPException(409, "The run is over")
        if claim["status"] != "waiting":
            raise HTTPException(409, f"Claim is {claim['status']}, not waiting")
        if run["claim_id"] and run["claim_id"] != claim_id:
            raise HTTPException(409, f"This run is only for {run['claim_id']}")
        if claim_id not in done and len(done) >= run["cap"]:
            raise HTTPException(409, f"The run's cap of {run['cap']} claims is reached")
        conn.execute(
            "INSERT OR IGNORE INTO run_claims (run_id, claim_id) VALUES (?, ?)",
            (run_id, claim_id),
        )
        conn.execute(
            "UPDATE claims SET status='in_progress', attempts=attempts+1 "
            "WHERE claim_id=?",
            (claim_id,),
        )
        set_todo_state(conn, claim_id, "in_progress", ("todo",))
    return {"attempt": claim["attempts"] + 1}


@router.post("/api/runs/{run_id}/finish", operation_id="finish_run")
def finish_run(run_id: int, finish: Finish) -> dict[str, str]:
    """End a run with its summary and requeue any claim it left in progress."""
    with connect() as conn:
        run_row(conn, run_id)
        sweep_stuck(conn)
        conn.execute(
            "UPDATE runs SET status='finished', summary=? WHERE id=?",
            (finish.summary, run_id),
        )
    return {"status": "finished"}
