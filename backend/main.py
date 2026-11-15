"""The UnderCover backend."""

import json
import sqlite3
from collections.abc import Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from backend import db
from backend.documents import Document, sections

INSTRUCTIONS = Path(__file__).parent / "instructions"
MAX_ATTEMPTS = 2


@asynccontextmanager
async def lifespan(_: FastAPI):  # noqa: ANN201
    """Seed the database on first start."""
    with db.session() as conn:
        if not db.is_seeded(conn):
            db.seed(conn)
    yield


app = FastAPI(title="UnderCover", lifespan=lifespan)


def get_db() -> Iterator[sqlite3.Connection]:
    """Give each request its own connection."""
    with db.session() as conn:
        yield conn


Db = Annotated[sqlite3.Connection, Depends(get_db)]


class Decision(BaseModel):
    """The agent's decision on a claim."""

    decision: Literal["approve", "decline", "refer"]
    payout: float = Field(ge=0)
    policy_section: str
    reason: str


class Payment(BaseModel):
    """An amount to pay on a claim."""

    amount: float


class SignOff(BaseModel):
    """The handler who signs off a payout."""

    handler_id: str


class Failure(BaseModel):
    """What went wrong while working a claim."""

    error: str


class Reading(BaseModel):
    """A section of a document to read."""

    document: Document
    number: int


class NewRun(BaseModel):
    """A run and the most claims it may work."""

    limit: int = Field(ge=1)


class TodoItem(BaseModel):
    """One item on a run's to-do list."""

    text: str
    status: Literal["todo", "in_progress", "done", "for_handler"]


class Todos(BaseModel):
    """A run's whole to-do list."""

    items: list[TodoItem]


class Summary(BaseModel):
    """A run's closing summary for the handlers."""

    summary: str


def record(conn: sqlite3.Connection, kind: str, record_id: str) -> dict[str, Any]:
    """Return one record, such as a policy or a customer."""
    row = conn.execute(
        "SELECT body FROM records WHERE kind = ? AND id = ?", (kind, record_id)
    ).fetchone()
    if row is None:
        raise HTTPException(404, f"No {kind} {record_id}")
    return json.loads(row["body"])


def claim_row(conn: sqlite3.Connection, claim_id: str) -> sqlite3.Row:
    """Return a claim's row or a 404."""
    row = conn.execute(
        "SELECT * FROM claims WHERE claim_id = ?", (claim_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(404, f"No claim {claim_id}")
    return row


def add_step(conn: sqlite3.Connection, claim_id: str, kind: str, text: str) -> None:
    """Record a step on a claim."""
    conn.execute(
        "INSERT INTO steps (claim_id, kind, text) VALUES (?, ?, ?)",
        (claim_id, kind, text),
    )


def approval_limit(conn: sqlite3.Connection) -> float:
    """Return the payout above which a handler must sign off."""
    return record(conn, "company", "company")["payout_approval_limit"]


def money(amount: float) -> str:
    """Format an amount in US dollars."""
    return f"${amount:,.2f}"


def claim_view(conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    """Return a claim with its state and its steps."""
    steps = conn.execute(
        "SELECT kind, text, created_at FROM steps WHERE claim_id = ? ORDER BY id",
        (row["claim_id"],),
    ).fetchall()
    state = {
        key: row[key]
        for key in (
            "status",
            "decision",
            "payout",
            "reason",
            "policy_section",
            "attempts",
            "paid",
            "signed_off_by",
        )
    }
    return {**json.loads(row["body"]), **state, "steps": [dict(s) for s in steps]}


@app.get("/api/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the backend is running."""
    return {"status": "ok"}


@app.post("/api/reseed", operation_id="reseed")
def reseed(conn: Db) -> dict[str, int]:
    """Reset the database to the seed data."""
    db.seed(conn)
    count = conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0]
    return {"claims": count}


@app.get("/api/claims", operation_id="list_claims")
def list_claims(conn: Db) -> list[dict[str, Any]]:
    """List every claim with where it stands."""
    rows = conn.execute("SELECT * FROM claims ORDER BY claim_id").fetchall()
    keys = ("claim_id", "claim_type", "summary", "amount_claimed")
    return [
        {k: json.loads(r["body"])[k] for k in keys}
        | {k: r[k] for k in ("status", "decision", "payout", "paid")}
        for r in rows
    ]


@app.get("/api/claims/{claim_id}", operation_id="get_claim")
def get_claim(claim_id: str, conn: Db) -> dict[str, Any]:
    """Get one claim in full, with its steps."""
    return claim_view(conn, claim_row(conn, claim_id))


@app.post("/api/claims/{claim_id}/look-up-policy", operation_id="look_up_policy")
def look_up_policy(claim_id: str, conn: Db) -> dict[str, Any]:
    """Get the claim's policy and the plan's limits."""
    policy = record(
        conn, "policy", json.loads(claim_row(conn, claim_id)["body"])["policy_id"]
    )
    add_step(conn, claim_id, "policy", f"Looked up policy {policy['policy_id']}")
    return {"policy": policy, "plan": record(conn, "plan", policy["plan"])}


@app.post("/api/claims/{claim_id}/look-up-history", operation_id="look_up_history")
def look_up_history(claim_id: str, conn: Db) -> dict[str, Any]:
    """Get the customer's earlier claims, without their contact details."""
    customer = record(
        conn, "customer", json.loads(claim_row(conn, claim_id)["body"])["customer_id"]
    )
    history = customer["previous_claims"]
    add_step(
        conn,
        claim_id,
        "history",
        f"Checked claim history: {len(history)} earlier claims",
    )
    return {"customer_id": customer["customer_id"], "previous_claims": history}


@app.post("/api/claims/{claim_id}/read-section", operation_id="read_section")
def read_section(claim_id: str, reading: Reading, conn: Db) -> dict[str, str | int]:
    """Read one numbered section of the claims manual or the policy wording."""
    claim_row(conn, claim_id)
    for section in sections(reading.document):
        if section["number"] == reading.number:
            add_step(
                conn,
                claim_id,
                "read",
                f"Read {reading.document} section {section['number']}:"
                f" {section['title']}",
            )
            return section
    raise HTTPException(404, f"No section {reading.number} in {reading.document}")


@app.get("/api/documents/{document}/sections", operation_id="list_sections")
def list_sections(document: Document) -> list[dict[str, str | int]]:
    """List the numbered sections of the claims manual or the policy wording."""
    return [{"number": s["number"], "title": s["title"]} for s in sections(document)]


@app.post("/api/claims/{claim_id}/decision", operation_id="decide_claim")
def decide_claim(claim_id: str, decision: Decision, conn: Db) -> dict[str, str]:
    """Record the decision on a claim that is in progress."""
    row = claim_row(conn, claim_id)
    if row["status"] != "in_progress":
        raise HTTPException(409, f"Claim is {row['status']}, not in progress")
    approved = decision.decision == "approve"
    if approved != (decision.payout > 0):
        raise HTTPException(422, "Only an approval carries a payout above zero")
    needs_signoff = approved and decision.payout > approval_limit(conn)
    status = "awaiting_signoff" if needs_signoff else "decided"
    conn.execute(
        "UPDATE claims SET status = ?, decision = ?, payout = ?, reason = ?,"
        " policy_section = ? WHERE claim_id = ?",
        (
            status,
            decision.decision,
            decision.payout,
            decision.reason,
            decision.policy_section,
            claim_id,
        ),
    )
    add_step(
        conn,
        claim_id,
        "decision",
        f"Decided: {decision.decision}, payout {money(decision.payout)}",
    )
    return {"status": status}


@app.post("/api/claims/{claim_id}/payment", operation_id="pay_claim")
def pay_claim(claim_id: str, payment: Payment, conn: Db) -> dict[str, float]:
    """Pay an approved claim, once, for exactly the approved payout."""
    row = claim_row(conn, claim_id)
    if row["status"] == "awaiting_signoff":
        raise HTTPException(409, "A handler must sign off this payout first")
    if row["decision"] != "approve" or row["status"] != "decided":
        raise HTTPException(409, "Only an approved claim can be paid")
    if row["paid"] is not None:
        raise HTTPException(409, "Claim is already paid")
    if abs(payment.amount - row["payout"]) > 0.005:  # noqa: PLR2004
        raise HTTPException(409, f"The payout is {money(row['payout'])}")
    conn.execute(
        "UPDATE claims SET paid = ? WHERE claim_id = ?", (payment.amount, claim_id)
    )
    add_step(conn, claim_id, "payment", f"Paid {money(payment.amount)}")
    return {"paid": payment.amount}


@app.get("/api/handlers", operation_id="list_handlers")
def list_handlers(conn: Db) -> list[dict[str, Any]]:
    """List the handlers who can sign off a payout above the limit."""
    rows = conn.execute("SELECT body FROM records WHERE kind = 'handler'").fetchall()
    handlers = [json.loads(r["body"]) for r in rows]
    return [
        {"handler_id": h["handler_id"], "name": h["name"]}
        for h in handlers
        if h["can_approve_over_limit"]
    ]


@app.post("/api/claims/{claim_id}/sign-off", operation_id="sign_off_claim")
def sign_off_claim(claim_id: str, sign_off: SignOff, conn: Db) -> dict[str, str]:
    """Let a handler sign off a payout above the approval limit."""
    row = claim_row(conn, claim_id)
    if row["status"] != "awaiting_signoff":
        raise HTTPException(409, "Claim is not waiting for sign-off")
    handler = record(conn, "handler", sign_off.handler_id)
    if not handler["can_approve_over_limit"]:
        raise HTTPException(403, f"{handler['name']} cannot sign off this payout")
    conn.execute(
        "UPDATE claims SET status = 'decided', signed_off_by = ? WHERE claim_id = ?",
        (handler["name"], claim_id),
    )
    add_step(conn, claim_id, "sign-off", f"Signed off by {handler['name']}")
    return {"signed_off_by": handler["name"]}


@app.post("/api/claims/{claim_id}/failure", operation_id="fail_claim")
def fail_claim(claim_id: str, failure: Failure, conn: Db) -> dict[str, str | int]:
    """Requeue a failed claim, or leave it for a handler on the second failure."""
    row = claim_row(conn, claim_id)
    if row["status"] != "in_progress":
        raise HTTPException(409, f"Claim is {row['status']}, not in progress")
    attempts = row["attempts"] + 1
    status = "waiting" if attempts < MAX_ATTEMPTS else "for_handler"
    conn.execute(
        "UPDATE claims SET status = ?, attempts = ? WHERE claim_id = ?",
        (status, attempts, claim_id),
    )
    add_step(conn, claim_id, "failure", f"Attempt {attempts} failed: {failure.error}")
    return {"status": status, "attempts": attempts}


def run_row(conn: sqlite3.Connection, run_id: int) -> sqlite3.Row:
    """Return a run's row or a 404."""
    row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    if row is None:
        raise HTTPException(404, f"No run {run_id}")
    return row


def run_view(conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    """Return a run with its to-do list and the claims it has taken on."""
    todos = conn.execute(
        "SELECT text, status FROM todos WHERE run_id = ? ORDER BY position",
        (row["id"],),
    ).fetchall()
    claims = conn.execute(
        "SELECT claim_id FROM run_claims WHERE run_id = ? ORDER BY claim_id",
        (row["id"],),
    ).fetchall()
    return {
        "id": row["id"],
        "limit": row["cap"],
        "summary": row["summary"],
        "finished": bool(row["finished"]),
        "created_at": row["created_at"],
        "todos": [dict(t) for t in todos],
        "claims": [c["claim_id"] for c in claims],
    }


@app.post("/api/runs", operation_id="start_run")
def start_run(new_run: NewRun, conn: Db) -> dict[str, Any]:
    """Start a run that may work at most the given number of claims."""
    cursor = conn.execute("INSERT INTO runs (cap) VALUES (?)", (new_run.limit,))
    return run_view(conn, run_row(conn, cursor.lastrowid or 0))


@app.get("/api/runs/current", operation_id="get_current_run")
def get_current_run(conn: Db) -> dict[str, Any] | None:
    """Get the latest run with its to-do list, or null before any run."""
    row = conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 1").fetchone()
    return None if row is None else run_view(conn, row)


@app.get("/api/runs/{run_id}", operation_id="get_run")
def get_run(run_id: int, conn: Db) -> dict[str, Any]:
    """Get a run with its to-do list."""
    return run_view(conn, run_row(conn, run_id))


@app.put("/api/runs/{run_id}/todos", operation_id="set_todos")
def set_todos(run_id: int, todos: Todos, conn: Db) -> dict[str, int]:
    """Replace the run's whole to-do list."""
    run_row(conn, run_id)
    conn.execute("DELETE FROM todos WHERE run_id = ?", (run_id,))
    conn.executemany(
        "INSERT INTO todos VALUES (?, ?, ?, ?)",
        [(run_id, i, t.text, t.status) for i, t in enumerate(todos.items)],
    )
    return {"items": len(todos.items)}


@app.get("/api/runs/{run_id}/waiting", operation_id="list_waiting_claims")
def list_waiting_claims(run_id: int, conn: Db) -> list[dict[str, Any]]:
    """List the waiting claims this run may work, within its cap."""
    run = run_row(conn, run_id)
    taken = {
        r["claim_id"]
        for r in conn.execute(
            "SELECT claim_id FROM run_claims WHERE run_id = ?", (run_id,)
        )
    }
    waiting = conn.execute(
        "SELECT * FROM claims WHERE status = 'waiting' ORDER BY claim_id"
    ).fetchall()
    retries = [r for r in waiting if r["claim_id"] in taken]
    fresh = [r for r in waiting if r["claim_id"] not in taken][
        : max(run["cap"] - len(taken), 0)
    ]
    keys = ("claim_id", "claim_type", "summary", "amount_claimed")
    return [{k: json.loads(r["body"])[k] for k in keys} for r in retries + fresh]


@app.post("/api/runs/{run_id}/claims/{claim_id}", operation_id="start_claim")
def start_claim(run_id: int, claim_id: str, conn: Db) -> dict[str, str]:
    """Take a waiting claim into the run, within its cap, and mark it in progress."""
    offered = {c["claim_id"] for c in list_waiting_claims(run_id, conn)}
    row = claim_row(conn, claim_id)
    if row["status"] != "waiting":
        raise HTTPException(409, f"Claim is {row['status']}, not waiting")
    if claim_id not in offered:
        raise HTTPException(409, "The run's cap is reached")
    conn.execute("INSERT OR IGNORE INTO run_claims VALUES (?, ?)", (run_id, claim_id))
    conn.execute(
        "UPDATE claims SET status = 'in_progress' WHERE claim_id = ?", (claim_id,)
    )
    add_step(conn, claim_id, "started", f"Started in run {run_id}")
    return {"status": "in_progress"}


@app.post("/api/runs/{run_id}/summary", operation_id="finish_run")
def finish_run(run_id: int, summary: Summary, conn: Db) -> dict[str, bool]:
    """Close the run with a summary for the handlers."""
    run_row(conn, run_id)
    conn.execute(
        "UPDATE runs SET summary = ?, finished = 1 WHERE id = ?",
        (summary.summary, run_id),
    )
    return {"finished": True}


@app.get("/api/instructions", operation_id="get_instructions")
def get_instructions() -> dict[str, str]:
    """Get the agent's instructions for running the queue and for working a claim."""
    return {
        "queue": (INSTRUCTIONS / "queue.md").read_text(),
        "claim": (INSTRUCTIONS / "claim.md").read_text(),
    }
