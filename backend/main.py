"""The UnderCover backend."""

import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException

from backend.db import DATA, connect, load
from backend.models import (
    AddOn,
    Amount,
    Claim,
    ClaimSummary,
    Decision,
    Handler,
    Payment,
    Plan,
    Policy,
    PreviousClaim,
    SignOff,
    Step,
    Text,
)

app = FastAPI(title="UnderCover")

PLANS = json.loads((DATA / "plans.json").read_text())
INSTRUCTIONS = Path(__file__).parent / "instructions.md"
APPROVAL_LIMIT = json.loads((DATA / "company.json").read_text())[
    "payout_approval_limit"
]


def database() -> Iterator[sqlite3.Connection]:
    """Yield a connection to the database for one request."""
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


Db = Annotated[sqlite3.Connection, Depends(database)]


def claim_row(db: sqlite3.Connection, claim_id: str) -> sqlite3.Row:
    """Fetch a claim's row, or raise 404."""
    row = db.execute("SELECT * FROM claims WHERE claim_id = ?", (claim_id,)).fetchone()
    if row is None:
        raise HTTPException(404, f"No claim {claim_id}")
    return row


def customer(db: sqlite3.Connection, customer_id: str) -> dict:
    """Fetch a customer's record."""
    row = db.execute(
        "SELECT data FROM customers WHERE customer_id = ?", (customer_id,)
    ).fetchone()
    return json.loads(row["data"])


def to_claim(db: sqlite3.Connection, row: sqlite3.Row) -> Claim:
    """Build the full claim from its row."""
    decision = None
    if row["decision"]:
        decision = Decision(
            decision=row["decision"],
            payout=row["payout"],
            reason=row["reason"],
            policy_section=row["policy_section"],
        )
    payment = None
    if row["paid_amount"] is not None:
        payment = Payment(amount=row["paid_amount"], signed_off_by=row["signed_off_by"])
    data = json.loads(row["data"])
    data.pop("status")
    return Claim(
        **data,
        customer_name=customer(db, row["customer_id"])["name"],
        status=row["status"],
        decision=decision,
        payment=payment,
    )


@app.get("/api/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the backend is running."""
    return {"status": "ok"}


@app.get("/api/claims", operation_id="list_claims")
def list_claims(db: Db) -> list[ClaimSummary]:
    """List every claim in queue order."""
    rows = db.execute("SELECT * FROM claims ORDER BY position").fetchall()
    summaries = []
    for row in rows:
        data = json.loads(row["data"])
        summaries.append(
            ClaimSummary(
                claim_id=row["claim_id"],
                customer_name=customer(db, row["customer_id"])["name"],
                claim_type=data["claim_type"],
                summary=data["summary"],
                submitted_on=data["submitted_on"],
                amount_claimed=data["amount_claimed"],
                status=row["status"],
                decision=row["decision"],
                payout=row["payout"],
            )
        )
    return summaries


@app.get("/api/claims/{claim_id}", operation_id="get_claim")
def get_claim(claim_id: str, db: Db) -> Claim:
    """Get a claim in full, with its decision and payment."""
    return to_claim(db, claim_row(db, claim_id))


@app.get("/api/claims/{claim_id}/policy", operation_id="get_policy")
def get_policy(claim_id: str, db: Db) -> Policy:
    """Get the policy a claim is made under, with its plan and add-ons."""
    row = claim_row(db, claim_id)
    policy = json.loads(
        db.execute(
            "SELECT data FROM policies WHERE policy_id = ?", (row["policy_id"],)
        ).fetchone()["data"]
    )
    plan = next(p for p in PLANS["plans"] if p["plan"] == policy["plan"])
    add_ons = [a for a in PLANS["add_ons"] if a["add_on"] in policy["add_ons"]]
    return Policy(
        **{**policy, "plan": Plan(**plan), "add_ons": [AddOn(**a) for a in add_ons]}
    )


@app.get("/api/claims/{claim_id}/history", operation_id="get_claim_history")
def get_claim_history(claim_id: str, db: Db) -> list[PreviousClaim]:
    """Get the customer's earlier claims, without their contact details."""
    row = claim_row(db, claim_id)
    return [
        PreviousClaim(**c) for c in customer(db, row["customer_id"])["previous_claims"]
    ]


@app.get("/api/policy-wording", operation_id="get_policy_wording")
def get_policy_wording() -> Text:
    """Get the policy wording, the contract with the customer."""
    return Text(text=(DATA / "policy_wording.md").read_text())


@app.get("/api/instructions", operation_id="get_instructions")
def get_instructions() -> Text:
    """Get the UnderCover Agent's instructions."""
    return Text(text=INSTRUCTIONS.read_text())


@app.get("/api/handlers", operation_id="list_handlers")
def list_handlers() -> list[Handler]:
    """List the claims handlers who can sign off payments."""
    return [Handler(**h) for h in load("handlers.json")]


def conflict(message: str) -> HTTPException:
    """Return a 409 for a step taken out of order."""
    return HTTPException(409, message)


@app.post("/api/claims/{claim_id}/start", operation_id="start_claim")
def start_claim(claim_id: str, db: Db) -> Claim:
    """Take a waiting claim from the queue and mark it in progress."""
    if claim_row(db, claim_id)["status"] != "waiting":
        raise conflict(f"{claim_id} is not waiting")
    db.execute(
        "UPDATE claims SET status = 'in_progress' WHERE claim_id = ?", (claim_id,)
    )
    return get_claim(claim_id, db)


@app.get("/api/claims/{claim_id}/steps", operation_id="list_steps")
def list_steps(claim_id: str, db: Db) -> list[Step]:
    """List the agent's steps on a claim, oldest first."""
    claim_row(db, claim_id)
    rows = db.execute(
        "SELECT id, text, created_at FROM steps WHERE claim_id = ? ORDER BY id",
        (claim_id,),
    ).fetchall()
    return [Step(**row) for row in rows]


@app.post("/api/claims/{claim_id}/steps", operation_id="add_step")
def add_step(claim_id: str, step: Text, db: Db) -> Step:
    """Record one step the agent took on a claim."""
    claim_row(db, claim_id)
    cursor = db.execute(
        "INSERT INTO steps (claim_id, text) VALUES (?, ?)", (claim_id, step.text)
    )
    row = db.execute(
        "SELECT id, text, created_at FROM steps WHERE id = ?", (cursor.lastrowid,)
    ).fetchone()
    return Step(**row)


@app.post("/api/claims/{claim_id}/decision", operation_id="record_decision")
def record_decision(claim_id: str, decision: Decision, db: Db) -> Claim:
    """Approve, decline or refer a claim in progress, with the payout and reasons."""
    row = claim_row(db, claim_id)
    if row["status"] != "in_progress" or row["decision"]:
        raise conflict(f"{claim_id} is not in progress or is already decided")
    status = "in_progress"
    if decision.decision != "approve":
        status = "decided"
    elif decision.payout > APPROVAL_LIMIT:
        status = "awaiting_signoff"
    db.execute(
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
    return get_claim(claim_id, db)


@app.post("/api/claims/{claim_id}/payment", operation_id="pay_claim")
def pay_claim(claim_id: str, payment: Amount, db: Db) -> Claim:
    """Pay the approved payout on a claim that needs no sign-off."""
    row = claim_row(db, claim_id)
    if row["status"] == "awaiting_signoff":
        raise conflict(
            f"{claim_id} pays over ${APPROVAL_LIMIT:,.2f} and needs a handler's"
            " sign-off. The payment is held until then."
        )
    if row["decision"] != "approve" or row["status"] != "in_progress":
        raise conflict(f"{claim_id} is not an approved claim waiting for payment")
    if payment.amount != row["payout"]:
        raise conflict(
            f"The payment must be the approved payout, ${row['payout']:,.2f}"
        )
    db.execute(
        "UPDATE claims SET status = 'decided', paid_amount = ? WHERE claim_id = ?",
        (payment.amount, claim_id),
    )
    return get_claim(claim_id, db)


@app.post("/api/claims/{claim_id}/signoff", operation_id="sign_off_claim")
def sign_off_claim(claim_id: str, sign_off: SignOff, db: Db) -> Claim:
    """Sign off a payout over the approval limit, which releases the payment."""
    row = claim_row(db, claim_id)
    if row["status"] != "awaiting_signoff":
        raise conflict(f"{claim_id} is not waiting for sign-off")
    handler = next(
        (h for h in load("handlers.json") if h["handler_id"] == sign_off.handler_id),
        None,
    )
    if handler is None or not handler["can_approve_over_limit"]:
        raise HTTPException(422, f"{sign_off.handler_id} cannot sign off payments")
    db.execute(
        "UPDATE claims SET status = 'decided', paid_amount = payout,"
        " signed_off_by = ? WHERE claim_id = ?",
        (handler["name"], claim_id),
    )
    return get_claim(claim_id, db)
