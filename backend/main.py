"""The UnderCover backend."""

import json
import sqlite3

from fastapi import FastAPI, HTTPException

from backend import db
from backend.schemas import (
    Claim,
    ClaimSummary,
    Customer,
    Handler,
    PlanLimits,
    Policy,
    PolicyWording,
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


def _require_claim(claim_id: str) -> sqlite3.Row:
    row = db.fetch_claim(claim_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")
    return row


@app.get("/api/claims", operation_id="list_claims")
def list_claims() -> list[ClaimSummary]:
    """List every claim in the queue."""
    return [_claim_summary(row) for row in db.fetch_claims()]


@app.get("/api/claims/{claim_id}", operation_id="get_claim")
def get_claim(claim_id: str) -> Claim:
    """Return a claim with its customer, policy and plan."""
    return _claim(_require_claim(claim_id))


@app.get("/api/policy-wording", operation_id="get_policy_wording")
def get_policy_wording() -> PolicyWording:
    """Return the policy wording."""
    return PolicyWording(content=db.policy_wording())


@app.get("/api/handlers", operation_id="list_handlers")
def list_handlers() -> list[Handler]:
    """List the claims handlers."""
    return [Handler(**dict(row)) for row in db.fetch_handlers()]
