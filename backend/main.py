"""The UnderCover backend."""

import json
import sqlite3

from fastapi import FastAPI, HTTPException

from backend import claims, db
from backend.schemas import (
    Claim,
    ClaimEvent,
    ClaimSummary,
    Customer,
    DecideClaimRequest,
    Handler,
    PayClaimRequest,
    PaymentResult,
    PlanLimits,
    Policy,
    PolicyWording,
    SignOffRequest,
)

app = FastAPI(title="UnderCover")


@app.get("/api/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the backend is running."""
    return {"status": "ok"}


def _claim_summary(row: sqlite3.Row) -> ClaimSummary:
    return ClaimSummary(
        claim_id=row["claim_id"],
        claim_type=row["claim_type"],
        summary=row["summary"],
        submitted_on=row["submitted_on"],
        amount_claimed=row["amount_claimed"],
        status=row["status"],
        decision=row["decision"],
        payout=row["payout"],
    )


def _customer(row: sqlite3.Row) -> Customer:
    return Customer(
        customer_id=row["customer_id"],
        name=row["name"],
        email=row["email"],
        phone=row["phone"],
        date_of_birth=row["date_of_birth"],
        address=json.loads(row["address"]),
        customer_since=row["customer_since"],
        previous_claims=json.loads(row["previous_claims"]),
    )


def _policy(row: sqlite3.Row) -> Policy:
    plan_row = db.fetch_plan(row["plan"])
    if plan_row is None:
        raise HTTPException(status_code=404, detail=f"Plan {row['plan']} not found")
    return Policy(
        policy_id=row["policy_id"],
        customer_id=row["customer_id"],
        plan=row["plan"],
        add_ons=json.loads(row["add_ons"]),
        purchased_on=row["purchased_on"],
        sold_through=row["sold_through"],
        trip=json.loads(row["trip"]),
        travelers=json.loads(row["travelers"]),
        status=row["status"],
        plan_limits=PlanLimits(**dict(plan_row)),
    )


def _claim(row: sqlite3.Row) -> Claim:
    customer_row = db.fetch_customer(row["customer_id"])
    policy_row = db.fetch_policy(row["policy_id"])
    if customer_row is None or policy_row is None:
        raise HTTPException(
            status_code=404, detail="Claim's customer or policy not found"
        )
    return Claim(
        claim_id=row["claim_id"],
        policy_id=row["policy_id"],
        customer_id=row["customer_id"],
        claim_type=row["claim_type"],
        submitted_on=row["submitted_on"],
        incident_date=row["incident_date"],
        incident_location=row["incident_location"],
        summary=row["summary"],
        story=row["story"],
        items=json.loads(row["items"]),
        amount_claimed=row["amount_claimed"],
        documents=json.loads(row["documents"]),
        status=row["status"],
        decision=row["decision"],
        payout=row["payout"],
        reason=row["reason"],
        reference=row["reference"],
        signed_off_by=row["signed_off_by"],
        paid_amount=row["paid_amount"],
        customer=_customer(customer_row),
        policy=_policy(policy_row),
    )


@app.get("/api/claims", operation_id="list_claims")
def list_claims() -> list[ClaimSummary]:
    """List every claim in the queue."""
    return [_claim_summary(row) for row in db.fetch_claims()]


@app.get("/api/claims/{claim_id}", operation_id="get_claim")
def get_claim(claim_id: str) -> Claim:
    """Return a claim with its customer, policy and plan."""
    return _claim(db.require_claim(claim_id))


@app.get("/api/policy-wording", operation_id="get_policy_wording")
def get_policy_wording() -> PolicyWording:
    """Return the policy wording."""
    return PolicyWording(content=db.policy_wording())


@app.get("/api/handlers", operation_id="list_handlers")
def list_handlers() -> list[Handler]:
    """List the claims handlers."""
    return [Handler(**dict(row)) for row in db.fetch_handlers()]


@app.get("/api/claims/{claim_id}/events", operation_id="list_claim_events")
def list_claim_events(claim_id: str) -> list[ClaimEvent]:
    """List what the agent or a handler has done on a claim, in order."""
    db.require_claim(claim_id)
    return [ClaimEvent(**dict(row)) for row in db.fetch_events(claim_id)]


@app.post("/api/claims/{claim_id}/decide", operation_id="decide_claim")
def decide_claim(claim_id: str, request: DecideClaimRequest) -> Claim:
    """Record a decision on a claim: approve, decline or refer."""
    claims.decide_claim(
        claim_id, request.decision, request.payout, request.reason, request.reference
    )
    return _claim(db.require_claim(claim_id))


@app.post("/api/claims/{claim_id}/pay", operation_id="pay_claim")
def pay_claim(claim_id: str, request: PayClaimRequest) -> PaymentResult:
    """Pay an approved claim, or hold it for sign-off if it's over the limit."""
    return claims.pay_claim(claim_id, request.amount)


@app.post("/api/claims/{claim_id}/sign-off", operation_id="sign_off_claim")
def sign_off_claim(claim_id: str, request: SignOffRequest) -> PaymentResult:
    """Sign off a claim that's waiting for a handler, releasing its payment."""
    return claims.sign_off_claim(claim_id, request.handler_id)
