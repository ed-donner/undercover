"""The UnderCover backend."""

import json
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel, Field

from agent import main as agent
from backend import db

INSTRUCTIONS = Path(__file__).resolve().parent / "instructions.md"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    db.init()
    yield


app = FastAPI(title="UnderCover", lifespan=lifespan)


def record(connection: sqlite3.Connection, kind: str, record_id: str) -> Any:
    row = connection.execute(
        "SELECT data FROM records WHERE kind = ? AND id = ?", (kind, record_id)
    ).fetchone()
    if row is None:
        raise HTTPException(404, f"There is no {kind} {record_id}.")
    return json.loads(row["data"])


def claim_row(connection: sqlite3.Connection, claim_id: str) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM claims WHERE claim_id = ?", (claim_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(404, f"There is no claim {claim_id}.")
    return row


def claim_view(row: sqlite3.Row) -> dict[str, Any]:
    decision = None
    if row["decision"] is not None:
        decision = {
            "decision": row["decision"],
            "payout": row["payout"],
            "reason": row["reason"],
            "policy_section": row["policy_section"],
            "decided_at": row["decided_at"],
        }
    sign_off = None
    if row["signed_off_by"] is not None:
        sign_off = {
            "handler_id": row["signed_off_by"],
            "signed_off_at": row["signed_off_at"],
        }
    payment = None
    if row["paid_amount"] is not None:
        payment = {"amount": row["paid_amount"], "paid_at": row["paid_at"]}
    return {
        **json.loads(row["data"]),
        "status": row["status"],
        "decision": decision,
        "sign_off": sign_off,
        "payment": payment,
    }


@app.get("/api/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the backend is running."""
    return {"status": "ok"}


@app.get("/api/claims", operation_id="list_claims")
def list_claims() -> list[dict[str, Any]]:
    """List the claims queue with where each claim stands."""
    with db.connect() as connection:
        rows = connection.execute("SELECT * FROM claims ORDER BY claim_id").fetchall()
    keys = ["claim_id", "claim_type", "summary", "amount_claimed", "submitted_on"]
    claims = []
    for row in rows:
        data = json.loads(row["data"])
        claims.append(
            {key: data[key] for key in keys}
            | {key: row[key] for key in ["status", "decision", "payout"]}
        )
    return claims


@app.get("/api/claims/{claim_id}", operation_id="get_claim")
def get_claim(claim_id: str) -> dict[str, Any]:
    """Get one claim in full, with its decision, sign-off and payment."""
    with db.connect() as connection:
        return claim_view(claim_row(connection, claim_id))


@app.get("/api/policies/{policy_id}", operation_id="get_policy")
def get_policy(policy_id: str) -> dict[str, Any]:
    """Get a policy with its plan's limits and its add-ons."""
    with db.connect() as connection:
        policy = record(connection, "policy", policy_id)
        plans = record(connection, "settings", "plans")
    plan = next(plan for plan in plans["plans"] if plan["plan"] == policy["plan"])
    add_ons = [a for a in plans["add_ons"] if a["add_on"] in policy["add_ons"]]
    return policy | {
        "plan_details": plan,
        "deductible_applies_to": plans["deductible_applies_to"],
        "add_on_details": add_ons,
    }


@app.get("/api/customers/{customer_id}/claims", operation_id="get_claim_history")
def get_claim_history(customer_id: str) -> dict[str, Any]:
    """Get a customer's earlier claims, without their personal details."""
    with db.connect() as connection:
        customer = record(connection, "customer", customer_id)
    return {
        "customer_id": customer_id,
        "customer_since": customer["customer_since"],
        "previous_claims": customer["previous_claims"],
    }


@app.get("/api/policy-wording", operation_id="get_policy_wording")
def get_policy_wording() -> dict[str, str]:
    """Get the policy wording that decisions must follow."""
    with db.connect() as connection:
        text = record(connection, "settings", "policy_wording")
        company = record(connection, "settings", "company")
    return {"version": company["policy_wording_version"], "text": text}


@app.get("/api/instructions", operation_id="get_instructions")
def get_instructions() -> dict[str, str]:
    """Get the UnderCover Agent's instructions."""
    return {"text": INSTRUCTIONS.read_text(encoding="utf-8")}


@app.get("/api/handlers", operation_id="list_handlers")
def list_handlers() -> list[dict[str, Any]]:
    """List the claims handlers."""
    with db.connect() as connection:
        rows = connection.execute(
            "SELECT data FROM records WHERE kind = 'handler' ORDER BY id"
        ).fetchall()
    return [json.loads(row["data"]) for row in rows]


class Step(BaseModel):
    kind: Literal["tool_call", "tool_result", "reply", "error"]
    text: str


class Decision(BaseModel):
    decision: Literal["approve", "decline", "refer"]
    payout: float = Field(ge=0)
    reason: str = Field(min_length=1)
    policy_section: str = Field(min_length=1)


class Payment(BaseModel):
    amount: float = Field(gt=0)


class SignOff(BaseModel):
    handler_id: str


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def money(amount: float) -> str:
    return f"${amount:,.2f}"


def approval_limit(connection: sqlite3.Connection) -> float:
    return record(connection, "settings", "company")["payout_approval_limit"]


def add_step_row(connection: sqlite3.Connection, claim_id: str, step: Step) -> None:
    connection.execute(
        "INSERT INTO steps (claim_id, kind, text, created_at) VALUES (?, ?, ?, ?)",
        (claim_id, step.kind, step.text, now()),
    )


def pay(connection: sqlite3.Connection, row: sqlite3.Row, amount: float) -> None:
    if row["decision"] != "approve":
        raise HTTPException(409, "Only an approved claim can be paid.")
    if row["paid_amount"] is not None:
        raise HTTPException(409, "This claim has already been paid.")
    if round(amount, 2) != round(row["payout"], 2):
        raise HTTPException(
            409, f"The amount must equal the approved payout of {money(row['payout'])}."
        )
    limit = approval_limit(connection)
    if amount > limit and row["signed_off_by"] is None:
        raise HTTPException(
            409,
            f"A payout over {money(limit)} needs a handler's sign-off "
            "before it can be paid.",
        )
    connection.execute(
        "UPDATE claims SET paid_amount = ?, paid_at = ? WHERE claim_id = ?",
        (round(amount, 2), now(), row["claim_id"]),
    )


@app.post("/api/claims/{claim_id}/steps", operation_id="add_step")
def add_step(claim_id: str, step: Step) -> dict[str, str]:
    """Record one step of the agent's work on a claim."""
    with db.connect() as connection:
        claim_row(connection, claim_id)
        add_step_row(connection, claim_id, step)
    return {"status": "recorded"}


@app.get("/api/claims/{claim_id}/steps", operation_id="list_steps")
def list_steps(claim_id: str) -> list[dict[str, Any]]:
    """List the steps of the agent's latest run on a claim, in order."""
    with db.connect() as connection:
        claim_row(connection, claim_id)
        rows = connection.execute(
            "SELECT id, kind, text, created_at FROM steps WHERE claim_id = ? "
            "ORDER BY id",
            (claim_id,),
        ).fetchall()
    return [dict(row) for row in rows]


@app.post("/api/claims/{claim_id}/decision", operation_id="record_decision")
def record_decision(claim_id: str, decision: Decision) -> dict[str, Any]:
    """Approve, decline or refer a claim, with the payout and the reason."""
    if decision.decision != "approve" and decision.payout != 0:
        raise HTTPException(422, "A decline or a refer has a payout of 0.")
    with db.connect() as connection:
        row = claim_row(connection, claim_id)
        if row["decision"] is not None:
            raise HTTPException(409, f"Claim {claim_id} has already been decided.")
        over_limit = (
            decision.decision == "approve"
            and decision.payout > approval_limit(connection)
        )
        connection.execute(
            "UPDATE claims SET status = ?, decision = ?, payout = ?, reason = ?, "
            "policy_section = ?, decided_at = ? WHERE claim_id = ?",
            (
                "awaiting_sign_off" if over_limit else "decided",
                decision.decision,
                round(decision.payout, 2),
                decision.reason,
                decision.policy_section,
                now(),
                claim_id,
            ),
        )
        return claim_view(claim_row(connection, claim_id))


@app.post("/api/claims/{claim_id}/payment", operation_id="pay_claim")
def pay_claim(claim_id: str, payment: Payment) -> dict[str, Any]:
    """Pay an approved claim the given amount."""
    with db.connect() as connection:
        pay(connection, claim_row(connection, claim_id), payment.amount)
        return claim_view(claim_row(connection, claim_id))


@app.post("/api/claims/{claim_id}/sign-off", operation_id="sign_off")
def sign_off(claim_id: str, sign_off: SignOff) -> dict[str, Any]:
    """Sign off an approval over the limit as a handler, which pays the claim."""
    with db.connect() as connection:
        handler = record(connection, "handler", sign_off.handler_id)
        if not handler["can_approve_over_limit"]:
            raise HTTPException(403, f"{handler['name']} cannot sign off this claim.")
        row = claim_row(connection, claim_id)
        if row["status"] != "awaiting_sign_off":
            raise HTTPException(409, f"Claim {claim_id} is not waiting for sign-off.")
        connection.execute(
            "UPDATE claims SET status = 'decided', signed_off_by = ?, "
            "signed_off_at = ? WHERE claim_id = ?",
            (sign_off.handler_id, now(), claim_id),
        )
        row = claim_row(connection, claim_id)
        pay(connection, row, row["payout"])
        return claim_view(claim_row(connection, claim_id))


def start(connection: sqlite3.Connection, claim_id: str) -> bool:
    started = connection.execute(
        "UPDATE claims SET status = 'in_progress' "
        "WHERE claim_id = ? AND status = 'waiting'",
        (claim_id,),
    ).rowcount
    if started:
        connection.execute("DELETE FROM steps WHERE claim_id = ?", (claim_id,))
    return bool(started)


def work(claim_id: str) -> None:
    problem = None
    try:
        agent.run(claim_id, f"{claim_id}-{uuid4().hex[:8]}")
    except Exception as error:
        problem = f"The agent stopped with an error: {error}"
    with db.connect() as connection:
        if claim_row(connection, claim_id)["status"] == "in_progress":
            connection.execute(
                "UPDATE claims SET status = 'waiting' WHERE claim_id = ?", (claim_id,)
            )
            problem = problem or "The agent finished without recording a decision."
            problem += " The claim is back in the queue."
        if problem:
            add_step_row(connection, claim_id, Step(kind="error", text=problem))


def work_queue(claim_ids: list[str]) -> None:
    for claim_id in claim_ids:
        with db.connect() as connection:
            started = start(connection, claim_id)
        if started:
            work(claim_id)


@app.post("/api/claims/{claim_id}/run", operation_id="run_agent")
def run_agent(claim_id: str, background: BackgroundTasks) -> dict[str, str]:
    """Start the UnderCover Agent on a waiting claim."""
    with db.connect() as connection:
        claim_row(connection, claim_id)
        if not start(connection, claim_id):
            raise HTTPException(409, f"Claim {claim_id} is not waiting.")
    background.add_task(work, claim_id)
    return {"status": "in_progress"}


@app.post("/api/queue/run", operation_id="run_queue")
def run_queue(background: BackgroundTasks) -> dict[str, int]:
    """Start the UnderCover Agent on every waiting claim, one after another."""
    with db.connect() as connection:
        rows = connection.execute(
            "SELECT claim_id FROM claims WHERE status = 'waiting' ORDER BY claim_id"
        ).fetchall()
    claim_ids = [row["claim_id"] for row in rows]
    background.add_task(work_queue, claim_ids)
    return {"waiting": len(claim_ids)}
