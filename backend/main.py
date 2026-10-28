"""The UnderCover backend."""

import json
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException

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
