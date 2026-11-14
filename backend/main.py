"""The UnderCover backend."""

import json
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException

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
