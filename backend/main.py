"""The UnderCover backend."""

import json
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any, Literal, Self
from uuid import uuid4

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field, model_validator

import agent.main as agent
from backend import db

INSTRUCTIONS = Path(__file__).parent / "instructions.md"
DECISION_FIELDS = [
    "decision",
    "payout",
    "reason",
    "policy_section",
    "decided_at",
    "signed_off_by",
    "signed_off_at",
    "paid_amount",
    "paid_at",
]


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Seed the database on startup if it doesn't exist yet."""
    if not db.path().exists():
        db.seed()
    yield


app = FastAPI(title="UnderCover", lifespan=lifespan)
Db = Annotated[sqlite3.Connection, Depends(db.connection)]


def find(database: sqlite3.Connection, table: str, record_id: str) -> sqlite3.Row:
    """Return one row by id, or raise 404."""
    row = database.execute(
        f"SELECT * FROM {table} WHERE id = ?",  # noqa: S608
        (record_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(404, f"{record_id} was not found")
    return row


def claim_view(row: sqlite3.Row) -> dict[str, Any]:
    """Return a claim with its status, decision, sign-off and payment."""
    fields = {name: row[name] for name in DECISION_FIELDS}
    return json.loads(row["record"]) | {"status": row["status"]} | fields


@app.get("/api/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the backend is running."""
    return {"status": "ok"}


@app.get("/api/claims", operation_id="list_claims")
def list_claims(database: Db) -> list[dict[str, Any]]:
    """List the claims queue with each claim's status."""
    rows = database.execute("SELECT * FROM claims ORDER BY id").fetchall()
    keys = ["claim_id", "claim_type", "summary", "amount_claimed", "submitted_on"]
    claims = []
    for row in rows:
        record = json.loads(row["record"])
        claims.append(
            {key: record[key] for key in keys}
            | {"status": row["status"], "decision": row["decision"]}
        )
    return claims


@app.get("/api/claims/{claim_id}", operation_id="get_claim")
def get_claim(claim_id: str, database: Db) -> dict[str, Any]:
    """Get a claim in full, with its decision, sign-off and payment."""
    return claim_view(find(database, "claims", claim_id))


@app.get("/api/policies/{policy_id}", operation_id="get_policy")
def get_policy(policy_id: str, database: Db) -> dict[str, Any]:
    """Get a policy with its plan's limits and the details of its add-ons."""
    policy = json.loads(find(database, "policies", policy_id)["record"])
    plans = json.loads(db.setting(database, "plans"))
    plan = next(p for p in plans["plans"] if p["plan"] == policy["plan"])
    add_ons = [a for a in plans["add_ons"] if a["add_on"] in policy["add_ons"]]
    return policy | {
        "plan_details": plan,
        "deductible_applies_to": plans["deductible_applies_to"],
        "add_on_details": add_ons,
    }


@app.get("/api/customers/{customer_id}/history", operation_id="get_claim_history")
def get_claim_history(customer_id: str, database: Db) -> dict[str, Any]:
    """Get a customer's earlier claims, without their personal details."""
    customer = json.loads(find(database, "customers", customer_id)["record"])
    return {
        "customer_id": customer_id,
        "customer_since": customer["customer_since"],
        "previous_claims": customer["previous_claims"],
    }


@app.get("/api/policy-wording", operation_id="get_policy_wording")
def get_policy_wording(database: Db) -> dict[str, str]:
    """Get the policy wording that decisions follow."""
    return {"wording": db.setting(database, "policy_wording")}


@app.get("/api/instructions", operation_id="get_instructions")
def get_instructions() -> dict[str, str]:
    """Get the UnderCover Agent's instructions."""
    return {"instructions": INSTRUCTIONS.read_text(encoding="utf-8")}


@app.get("/api/handlers", operation_id="list_handlers")
def list_handlers(database: Db) -> list[dict[str, Any]]:
    """List the claims handlers and whether each can sign off large payouts."""
    rows = database.execute("SELECT record FROM handlers ORDER BY id").fetchall()
    keys = ["handler_id", "name", "role", "can_approve_over_limit"]
    return [{key: json.loads(row[0])[key] for key in keys} for row in rows]


class Decision(BaseModel):
    """The agent's decision on a claim."""

    decision: Literal["approve", "decline", "refer"]
    payout: float = Field(ge=0)
    reason: str
    policy_section: str

    @model_validator(mode="after")
    def only_approvals_pay(self) -> Self:
        """Check that a decline or a referral pays nothing."""
        if self.decision != "approve" and self.payout != 0:
            raise ValueError("A decline or a referral has a payout of 0")
        return self


class Payment(BaseModel):
    """A payment of an approved claim."""

    amount: float


class SignOff(BaseModel):
    """A handler's sign-off of a large payout."""

    handler_id: str


class Step(BaseModel):
    """One step the agent took on a claim."""

    kind: Literal["tool_call", "tool_result", "message", "error"]
    content: str


def approval_limit(database: sqlite3.Connection) -> float:
    """Return the payout above which a handler must sign off."""
    return json.loads(db.setting(database, "company"))["payout_approval_limit"]


def require_status(row: sqlite3.Row, status: str) -> None:
    """Raise 409 unless the claim is in the given status."""
    if row["status"] != status:
        raise HTTPException(409, f"{row['id']} is {row['status']}, not {status}")


def add_step(database: sqlite3.Connection, claim_id: str, kind: str, text: str) -> None:
    """Record one step on a claim."""
    database.execute(
        "INSERT INTO steps (claim_id, kind, content, created_at) VALUES (?, ?, ?, ?)",
        (claim_id, kind, text, db.now()),
    )


def run_in_background(claim_id: str) -> None:
    """Run the agent on a claim, with a new thread id."""
    agent.run(claim_id, f"{claim_id}-{uuid4().hex[:8]}")


@app.post("/api/claims/{claim_id}/run", operation_id="run_agent")
def run_agent(
    claim_id: str, database: Db, background: BackgroundTasks
) -> dict[str, str]:
    """Start the UnderCover Agent on a waiting claim."""
    require_status(find(database, "claims", claim_id), "waiting")
    background.add_task(run_in_background, claim_id)
    return {"status": "started"}


@app.post("/api/claims/{claim_id}/start", operation_id="start_claim")
def start_claim(claim_id: str, database: Db) -> dict[str, Any]:
    """Mark a waiting claim as in progress."""
    require_status(find(database, "claims", claim_id), "waiting")
    database.execute("DELETE FROM steps WHERE claim_id = ?", (claim_id,))
    database.execute(
        "UPDATE claims SET status = 'in_progress' WHERE id = ?", (claim_id,)
    )
    return claim_view(find(database, "claims", claim_id))


class Release(BaseModel):
    """Why a claim in progress goes back to the queue."""

    problem: str


@app.post("/api/claims/{claim_id}/release", operation_id="release_claim")
def release_claim(claim_id: str, release: Release, database: Db) -> dict[str, Any]:
    """Put a claim in progress back to waiting, recording the problem as a step."""
    require_status(find(database, "claims", claim_id), "in_progress")
    add_step(database, claim_id, "error", release.problem)
    database.execute("UPDATE claims SET status = 'waiting' WHERE id = ?", (claim_id,))
    return claim_view(find(database, "claims", claim_id))


@app.post("/api/claims/{claim_id}/steps", operation_id="record_step")
def record_step(claim_id: str, step: Step, database: Db) -> dict[str, str]:
    """Record a step the agent took on a claim."""
    find(database, "claims", claim_id)
    add_step(database, claim_id, step.kind, step.content)
    return {"status": "recorded"}


@app.get("/api/claims/{claim_id}/steps", operation_id="list_steps")
def list_steps(claim_id: str, database: Db) -> list[dict[str, Any]]:
    """List the steps the agent took on a claim, in order."""
    find(database, "claims", claim_id)
    rows = database.execute(
        "SELECT kind, content, created_at FROM steps WHERE claim_id = ? ORDER BY id",
        (claim_id,),
    ).fetchall()
    return [dict(row) for row in rows]


@app.post("/api/claims/{claim_id}/decision", operation_id="record_decision")
def record_decision(claim_id: str, decision: Decision, database: Db) -> dict[str, Any]:
    """Record the decision on a claim in progress."""
    require_status(find(database, "claims", claim_id), "in_progress")
    over_limit = decision.payout > approval_limit(database)
    status = "awaiting_signoff" if over_limit else "decided"
    database.execute(
        "UPDATE claims SET status = ?, decision = ?, payout = ?, reason = ?, "
        "policy_section = ?, decided_at = ? WHERE id = ?",
        (
            status,
            decision.decision,
            decision.payout,
            decision.reason,
            decision.policy_section,
            db.now(),
            claim_id,
        ),
    )
    return claim_view(find(database, "claims", claim_id))


def payment_problem(row: sqlite3.Row, amount: float, limit: float) -> str | None:
    """Return why a payment can't be made, or None if it can."""
    if row["decision"] is None:
        return f"{row['id']} has no decision yet"
    if row["decision"] != "approve":
        return f"{row['id']} was not approved, so nothing is paid"
    if row["paid_at"] is not None:
        return f"{row['id']} has already been paid"
    if row["payout"] > limit and row["signed_off_by"] is None:
        return (
            f"The payout is over ${limit:,.2f}, so the payment waits for a "
            "handler's sign-off"
        )
    if amount != row["payout"]:
        return f"The amount must be the approved payout of ${row['payout']:,.2f}"
    return None


@app.post("/api/claims/{claim_id}/payment", operation_id="pay_claim")
def pay_claim(claim_id: str, payment: Payment, database: Db) -> dict[str, Any]:
    """Pay the approved payout on a claim."""
    row = find(database, "claims", claim_id)
    problem = payment_problem(row, payment.amount, approval_limit(database))
    if problem:
        raise HTTPException(409, problem)
    database.execute(
        "UPDATE claims SET paid_amount = ?, paid_at = ? WHERE id = ?",
        (payment.amount, db.now(), claim_id),
    )
    return claim_view(find(database, "claims", claim_id))


@app.post("/api/claims/{claim_id}/signoff", operation_id="sign_off")
def sign_off(claim_id: str, signoff: SignOff, database: Db) -> dict[str, Any]:
    """Sign off a payout over the approval limit, as a handler with authority."""
    require_status(find(database, "claims", claim_id), "awaiting_signoff")
    handler = json.loads(find(database, "handlers", signoff.handler_id)["record"])
    if not handler["can_approve_over_limit"]:
        raise HTTPException(403, f"{handler['name']} can't sign off large payouts")
    database.execute(
        "UPDATE claims SET status = 'decided', signed_off_by = ?, signed_off_at = ? "
        "WHERE id = ?",
        (signoff.handler_id, db.now(), claim_id),
    )
    return claim_view(find(database, "claims", claim_id))
