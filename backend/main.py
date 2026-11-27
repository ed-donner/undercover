"""The UnderCover backend."""

import json
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException

from backend import db
from backend.models import (
    Claim,
    ClaimSummary,
    Customer,
    DecisionRequest,
    Handler,
    PaymentRequest,
    Policy,
    SignOffRequest,
    Step,
    StepRequest,
    Text,
)

INSTRUCTIONS = Path(__file__).parent / "instructions.md"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    db.init()
    yield


app = FastAPI(title="UnderCover", lifespan=lifespan)
Db = Annotated[sqlite3.Connection, Depends(db.get_db)]

CLAIM_QUERY = """
SELECT claims.claim_id, claims.status, claims.data,
       json_extract(customers.data, '$.name') AS customer_name
FROM claims JOIN customers USING (customer_id)
"""


def find(connection: sqlite3.Connection, table: str, key: str, value: str) -> Any:
    """Return the stored JSON record with this id, or raise 404."""
    row = connection.execute(
        f"SELECT data FROM {table} WHERE {key} = ?",  # noqa: S608
        (value,),
    ).fetchone()
    if not row:
        raise HTTPException(404, f"{value} not found")
    return json.loads(row["data"])


def claim_record(row: sqlite3.Row) -> dict[str, Any]:
    """Combine a claim row's stored data with its current state."""
    return json.loads(row["data"]) | {
        "status": row["status"],
        "customer_name": row["customer_name"],
    }


def load_claim(connection: sqlite3.Connection, claim_id: str) -> dict[str, Any]:
    """Return a claim with its state, or raise 404."""
    row = connection.execute(
        CLAIM_QUERY + "WHERE claims.claim_id = ?", (claim_id,)
    ).fetchone()
    if not row:
        raise HTTPException(404, f"{claim_id} not found")
    return claim_record(row)


@app.get("/api/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the backend is running."""
    return {"status": "ok"}


@app.get("/api/claims", operation_id="list_claims")
def list_claims(connection: Db) -> list[ClaimSummary]:
    """List every claim in the queue with where it stands."""
    rows = connection.execute(CLAIM_QUERY + "ORDER BY claims.claim_id").fetchall()
    return [ClaimSummary.model_validate(claim_record(row)) for row in rows]


@app.get("/api/claims/{claim_id}", operation_id="get_claim")
def get_claim(claim_id: str, connection: Db) -> Claim:
    """Get one claim in full, with its decision, payment and sign-off."""
    claim = load_claim(connection, claim_id)
    decision = connection.execute(
        "SELECT * FROM decisions WHERE claim_id = ?", (claim_id,)
    ).fetchone()
    payment = connection.execute(
        "SELECT amount, paid_at FROM payments WHERE claim_id = ?", (claim_id,)
    ).fetchone()
    sign_off = connection.execute(
        "SELECT handler_id, name AS handler_name, signed_at "
        "FROM sign_offs JOIN handlers USING (handler_id) WHERE claim_id = ?",
        (claim_id,),
    ).fetchone()
    return Claim.model_validate(
        claim
        | {
            "decision": decision and dict(decision),
            "payment": payment and dict(payment),
            "sign_off": sign_off and dict(sign_off),
        }
    )


@app.get("/api/policies/{policy_id}", operation_id="get_policy")
def get_policy(policy_id: str, connection: Db) -> Policy:
    """Get a policy with its plan's limits and its add-ons."""
    policy = find(connection, "policies", "policy_id", policy_id)
    plans = db.setting(connection, "plans")
    plan = next(p for p in plans["plans"] if p["plan"] == policy["plan"])
    add_ons = [a for a in plans["add_ons"] if a["add_on"] in policy["add_ons"]]
    return Policy.model_validate(
        policy
        | {
            "plan_details": plan,
            "add_on_details": add_ons,
            "deductible_applies_to": plans["deductible_applies_to"],
        }
    )


@app.get("/api/customers/{customer_id}", operation_id="get_customer")
def get_customer(customer_id: str, connection: Db) -> Customer:
    """Get a customer with their claim history."""
    return Customer.model_validate(
        find(connection, "customers", "customer_id", customer_id)
    )


@app.get("/api/policy-wording", operation_id="get_policy_wording")
def get_policy_wording(connection: Db) -> Text:
    """Get the policy wording, the contract that decisions follow."""
    return Text(text=db.setting(connection, "policy_wording"))


@app.get("/api/handlers", operation_id="list_handlers")
def list_handlers(connection: Db) -> list[Handler]:
    """List the claims handlers."""
    rows = connection.execute("SELECT * FROM handlers ORDER BY handler_id")
    return [Handler.model_validate(dict(row)) for row in rows]


@app.get("/api/instructions", operation_id="get_instructions")
def get_instructions() -> Text:
    """Get the UnderCover Agent's instructions."""
    return Text(text=INSTRUCTIONS.read_text(encoding="utf-8"))


def set_status(connection: sqlite3.Connection, claim_id: str, status: str) -> None:
    connection.execute(
        "UPDATE claims SET status = ? WHERE claim_id = ?", (status, claim_id)
    )


def require_status(claim_id: str, current: str, status: str) -> None:
    """Raise 409 unless the claim is in this state."""
    if current != status:
        raise HTTPException(409, f"{claim_id} is {current}, not {status}")


def payout_limit(connection: sqlite3.Connection) -> float:
    return db.setting(connection, "company")["payout_approval_limit"]


@app.post("/api/claims/{claim_id}/start", operation_id="start_claim")
def start_claim(claim_id: str, connection: Db) -> Claim:
    """Mark a waiting claim as in progress, before working on it."""
    require_status(claim_id, load_claim(connection, claim_id)["status"], "waiting")
    set_status(connection, claim_id, "in_progress")
    return get_claim(claim_id, connection)


@app.post("/api/claims/{claim_id}/release", operation_id="release_claim")
def release_claim(claim_id: str, connection: Db) -> Claim:
    """Put a claim in progress back in the queue, after a failed run."""
    status = load_claim(connection, claim_id)["status"]
    require_status(claim_id, status, "in_progress")
    set_status(connection, claim_id, "waiting")
    return get_claim(claim_id, connection)


@app.post("/api/claims/{claim_id}/steps", operation_id="record_step")
def record_step(claim_id: str, step: StepRequest, connection: Db) -> Step:
    """Record one step of the agent's work on a claim."""
    load_claim(connection, claim_id)
    row = connection.execute(
        "INSERT INTO steps (claim_id, kind, content) VALUES (?, ?, ?) RETURNING *",
        (claim_id, step.kind, step.content),
    ).fetchone()
    return Step.model_validate(dict(row))


@app.get("/api/claims/{claim_id}/steps", operation_id="list_steps")
def list_steps(claim_id: str, connection: Db) -> list[Step]:
    """List the steps of the agent's work on a claim, oldest first."""
    load_claim(connection, claim_id)
    rows = connection.execute(
        "SELECT * FROM steps WHERE claim_id = ? ORDER BY step_id", (claim_id,)
    )
    return [Step.model_validate(dict(row)) for row in rows]


@app.post("/api/claims/{claim_id}/decision", operation_id="record_decision")
def record_decision(claim_id: str, decision: DecisionRequest, connection: Db) -> Claim:
    """Record the decision on a claim in progress: approve, decline or refer."""
    status = load_claim(connection, claim_id)["status"]
    require_status(claim_id, status, "in_progress")
    if decision.decision == "approve" and decision.payout <= 0:
        raise HTTPException(422, "An approval needs a payout above 0")
    if decision.decision != "approve" and decision.payout != 0:
        raise HTTPException(422, f"A {decision.decision} has a payout of 0")
    connection.execute(
        "INSERT INTO decisions (claim_id, decision, payout, calculation, reasons, "
        "policy_section) VALUES (?, ?, ?, ?, ?, ?)",
        (
            claim_id,
            decision.decision,
            decision.payout,
            decision.calculation,
            decision.reasons,
            decision.policy_section,
        ),
    )
    over_limit = decision.payout > payout_limit(connection)
    set_status(connection, claim_id, "awaiting_signoff" if over_limit else "decided")
    return get_claim(claim_id, connection)


@app.post("/api/claims/{claim_id}/payment", operation_id="pay_claim")
def pay_claim(claim_id: str, payment: PaymentRequest, connection: Db) -> Claim:
    """Pay an approved claim its payout; over the limit it needs a sign-off first."""
    claim = get_claim(claim_id, connection)
    if not claim.decision or claim.decision.decision != "approve":
        raise HTTPException(409, f"{claim_id} has not been approved")
    if claim.payment:
        raise HTTPException(409, f"{claim_id} has already been paid")
    if payment.amount != claim.decision.payout:
        raise HTTPException(
            409,
            f"The approved payout is {claim.decision.payout:.2f}, "
            f"not {payment.amount:.2f}",
        )
    limit = payout_limit(connection)
    if not claim.sign_off and payment.amount > limit:
        raise HTTPException(
            403,
            f"A payout over ${limit:,.2f} needs a handler's sign-off. "
            "The payment waits until a handler signs off.",
        )
    connection.execute(
        "INSERT INTO payments (claim_id, amount) VALUES (?, ?)",
        (claim_id, payment.amount),
    )
    set_status(connection, claim_id, "decided")
    return get_claim(claim_id, connection)


@app.post("/api/claims/{claim_id}/sign-off", operation_id="sign_off")
def sign_off(claim_id: str, request: SignOffRequest, connection: Db) -> Claim:
    """Sign off a payout over the limit as a handler, which pays the claim."""
    claim = get_claim(claim_id, connection)
    require_status(claim_id, claim.status, "awaiting_signoff")
    handler = connection.execute(
        "SELECT * FROM handlers WHERE handler_id = ?", (request.handler_id,)
    ).fetchone()
    if not handler:
        raise HTTPException(404, f"{request.handler_id} not found")
    if not handler["can_approve_over_limit"]:
        raise HTTPException(403, f"{handler['name']} cannot sign off this payout")
    connection.execute(
        "INSERT INTO sign_offs (claim_id, handler_id) VALUES (?, ?)",
        (claim_id, request.handler_id),
    )
    payout = claim.decision.payout if claim.decision else 0
    return pay_claim(claim_id, PaymentRequest(amount=payout), connection)
