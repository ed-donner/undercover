"""The UnderCover backend."""

import json
import sqlite3
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from backend import lookup
from backend.db import (
    claim_row,
    connect,
    load_json,
    log_step,
    now,
    payout_limit,
    requeue,
    set_todo_state,
)
from backend.lookup import Document
from backend.runs import router as runs_router

INSTRUCTIONS = Path(__file__).parent / "instructions"

app = FastAPI(title="UnderCover")
app.include_router(runs_router)


class Decision(BaseModel):
    """The agent's decision on a claim."""

    decision: Literal["approve", "decline", "refer"]
    payout: float = Field(ge=0)
    section: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class Step(BaseModel):
    """One step the agent took on a claim."""

    tool: str
    summary: str


class Read(BaseModel):
    """A section of a document the agent read."""

    document: Document
    number: int


class Failure(BaseModel):
    """Why work on a claim failed."""

    reason: str


class Payment(BaseModel):
    """A payment of a claim."""

    amount: float = Field(ge=0)


class SignOff(BaseModel):
    """A handler's sign-off of a payout."""

    handler: str = Field(min_length=1)


def record(conn: sqlite3.Connection, table: str, key: str, value: str) -> dict:
    """Return a policy or customer record or answer 404."""
    row = conn.execute(
        f"SELECT data FROM {table} WHERE {key}=?",  # noqa: S608
        (value,),
    ).fetchone()
    if row is None:
        raise HTTPException(404, f"No {value}")
    return json.loads(row["data"])


@app.get("/api/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the backend is running."""
    return {"status": "ok"}


@app.get("/api/claims", operation_id="list_claims")
def list_claims() -> list[dict[str, Any]]:
    """List every claim with its status and decision."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT c.*, d.decision, d.payout FROM claims c "
            "LEFT JOIN decisions d ON d.claim_id = c.claim_id ORDER BY c.claim_id"
        ).fetchall()
    claims = []
    for row in rows:
        data = json.loads(row["data"])
        claims.append(
            {
                "claim_id": row["claim_id"],
                "claim_type": data["claim_type"],
                "summary": data["summary"],
                "amount_claimed": data["amount_claimed"],
                "status": row["status"],
                "attempts": row["attempts"],
                "decision": row["decision"],
                "payout": row["payout"],
            }
        )
    return claims


@app.get("/api/claims/{claim_id}", operation_id="get_claim")
def get_claim(claim_id: str) -> dict[str, Any]:
    """Return a claim in full, with its decision, payment, steps and sections read."""
    with connect() as conn:
        row = claim_row(conn, claim_id)
        decision = conn.execute(
            "SELECT decision, payout, section, reason, decided_at "
            "FROM decisions WHERE claim_id=?",
            (claim_id,),
        ).fetchone()
        payment = conn.execute(
            "SELECT amount, paid_at FROM payments WHERE claim_id=?", (claim_id,)
        ).fetchone()
        steps = conn.execute(
            "SELECT tool, summary, at FROM steps WHERE claim_id=? ORDER BY id",
            (claim_id,),
        ).fetchall()
        reads = conn.execute(
            "SELECT document, number, title FROM reads WHERE claim_id=? ORDER BY rowid",
            (claim_id,),
        ).fetchall()
    return {
        **json.loads(row["data"]),
        "status": row["status"],
        "attempts": row["attempts"],
        "signed_off_by": row["signed_off_by"],
        "decision": dict(decision) if decision else None,
        "payment": dict(payment) if payment else None,
        "steps": [dict(s) for s in steps],
        "reads": [dict(r) for r in reads],
    }


@app.get("/api/policies/{policy_id}", operation_id="get_policy")
def get_policy(policy_id: str) -> dict[str, Any]:
    """Return a policy with the terms of its plan and add-ons."""
    with connect() as conn:
        policy = record(conn, "policies", "policy_id", policy_id)
    plans = load_json("plans.json")
    return {
        **policy,
        "plan_terms": next(p for p in plans["plans"] if p["plan"] == policy["plan"]),
        "add_on_terms": [
            a for a in plans["add_ons"] if a["add_on"] in policy["add_ons"]
        ],
        "deductible_applies_to": plans["deductible_applies_to"],
    }


@app.get("/api/customers/{customer_id}/history", operation_id="get_claim_history")
def get_claim_history(customer_id: str) -> dict[str, Any]:
    """Return a customer's earlier claims."""
    with connect() as conn:
        customer = record(conn, "customers", "customer_id", customer_id)
    return {
        "customer_id": customer_id,
        "customer_since": customer["customer_since"],
        "previous_claims": customer["previous_claims"],
    }


@app.get("/api/sections/{document}", operation_id="list_sections")
def list_sections(document: Document) -> list[dict[str, str | int]]:
    """List the section numbers and titles of the manual or the wording."""
    return [
        {"number": s["number"], "title": s["title"]} for s in lookup.sections(document)
    ]


@app.get("/api/sections/{document}/search", operation_id="search_sections")
def search_sections(
    document: Document, query: Annotated[str, Query()]
) -> list[dict[str, str | int]]:
    """Find the sections of the manual or the wording that match a query."""
    return lookup.search(document, query)


@app.post("/api/claims/{claim_id}/reads", operation_id="read_section")
def read_section(claim_id: str, read: Read) -> lookup.Section:
    """Return one full section and record on the claim that it was read."""
    section = next(
        (s for s in lookup.sections(read.document) if s["number"] == read.number), None
    )
    if section is None:
        raise HTTPException(404, f"No section {read.number} in the {read.document}")
    with connect() as conn:
        claim_row(conn, claim_id)
        conn.execute(
            "INSERT OR IGNORE INTO reads (claim_id, document, number, title) "
            "VALUES (?, ?, ?, ?)",
            (claim_id, read.document, read.number, section["title"]),
        )
    return section


@app.post("/api/claims/{claim_id}/steps", operation_id="record_step")
def record_step(claim_id: str, step: Step) -> dict[str, str]:
    """Record a step the agent took on a claim."""
    with connect() as conn:
        claim_row(conn, claim_id)
        log_step(conn, claim_id, step.tool, step.summary)
    return {"status": "recorded"}


@app.post("/api/claims/{claim_id}/decision", operation_id="decide_claim")
def decide_claim(claim_id: str, decision: Decision) -> dict[str, str]:
    """Record the decision on a claim that is in progress, once only."""
    if decision.decision != "approve" and decision.payout:
        raise HTTPException(400, "Only an approval carries a payout")
    with connect() as conn:
        row = claim_row(conn, claim_id)
        if row["status"] != "in_progress":
            raise HTTPException(409, f"Claim is {row['status']}, not in progress")
        conn.execute(
            "INSERT INTO decisions VALUES (?, ?, ?, ?, ?, ?)",
            (
                claim_id,
                decision.decision,
                decision.payout,
                decision.section,
                decision.reason,
                now(),
            ),
        )
        over = decision.payout > payout_limit()
        status = (
            "awaiting_signoff" if decision.decision == "approve" and over else "decided"
        )
        conn.execute("UPDATE claims SET status=? WHERE claim_id=?", (status, claim_id))
        set_todo_state(conn, claim_id, "done", ("todo", "in_progress"))
    return {"status": status}


@app.post("/api/claims/{claim_id}/payment", operation_id="pay_claim")
def pay_claim(claim_id: str, payment: Payment) -> dict[str, float]:
    """Pay an approved claim once; a payout over the limit waits for sign-off."""
    with connect() as conn:
        row = claim_row(conn, claim_id)
        decision = conn.execute(
            "SELECT decision, payout FROM decisions WHERE claim_id=?", (claim_id,)
        ).fetchone()
        if decision is None or decision["decision"] != "approve":
            raise HTTPException(409, "Only an approved claim can be paid")
        if round(payment.amount, 2) != round(decision["payout"], 2):
            raise HTTPException(400, "The amount must equal the decided payout")
        if decision["payout"] > payout_limit() and not row["signed_off_by"]:
            raise HTTPException(409, "A payout over the limit needs sign-off")
        paid = conn.execute("SELECT 1 FROM payments WHERE claim_id=?", (claim_id,))
        if paid.fetchone():
            raise HTTPException(409, "Claim is already paid")
        conn.execute(
            "INSERT INTO payments VALUES (?, ?, ?)", (claim_id, payment.amount, now())
        )
    return {"paid": payment.amount}


@app.post("/api/claims/{claim_id}/sign-off", operation_id="sign_off_claim")
def sign_off_claim(claim_id: str, sign_off: SignOff) -> dict[str, str]:
    """Record a handler's sign-off of a payout that is waiting for it."""
    with connect() as conn:
        row = claim_row(conn, claim_id)
        if row["status"] != "awaiting_signoff":
            raise HTTPException(409, f"Claim is {row['status']}, not awaiting sign-off")
        conn.execute(
            "UPDATE claims SET status='decided', signed_off_by=? WHERE claim_id=?",
            (sign_off.handler, claim_id),
        )
    return {"status": "decided"}


@app.post("/api/claims/{claim_id}/failure", operation_id="fail_claim")
def fail_claim(claim_id: str, failure: Failure) -> dict[str, str]:
    """Requeue a claim that failed before it was decided, or leave it for a handler."""
    with connect() as conn:
        claim_row(conn, claim_id)
        log_step(conn, claim_id, "failure", failure.reason)
        status = requeue(conn, claim_id)
    return {"status": status}


@app.get("/api/instructions", operation_id="get_instructions")
def get_instructions() -> dict[str, str]:
    """Return the instructions for running the queue and for working a claim."""
    return {
        "queue_runner": (INSTRUCTIONS / "queue_runner.md").read_text(encoding="utf-8"),
        "claim": (INSTRUCTIONS / "claim.md").read_text(encoding="utf-8"),
    }
