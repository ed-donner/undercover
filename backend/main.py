"""The UnderCover backend."""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from sqlite3 import Connection, Row
from typing import Any

from fastapi import FastAPI, HTTPException

from backend.db import DATA, path, transaction
from backend.seed import seed

WORKFLOW_COLUMNS = (
    "status",
    "decision",
    "payout",
    "reason",
    "policy_section",
    "decided_at",
    "signed_off_by",
    "signed_off_at",
    "paid_amount",
    "paid_at",
)
QUEUE_FIELDS = (
    "claim_id",
    "claim_type",
    "summary",
    "submitted_on",
    "amount_claimed",
    "status",
    "decision",
    "payout",
    "paid_amount",
)
RECORD_QUERIES = {
    "policy": "SELECT record FROM policies WHERE policy_id = ?",
    "customer": "SELECT record FROM customers WHERE customer_id = ?",
    "handler": "SELECT record FROM handlers WHERE handler_id = ?",
}


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Seed the database when the backend starts without one."""
    if not path().exists():
        seed()
    yield


app = FastAPI(title="UnderCover", lifespan=lifespan)


def reference(name: str) -> Any:
    """Read one of the reference documents in data/."""
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def claim_from(row: Row) -> dict[str, Any]:
    """Combine a claim's record with where it stands."""
    return {**json.loads(row["record"]), **{key: row[key] for key in WORKFLOW_COLUMNS}}


def queue_entry(row: Row) -> dict[str, Any]:
    """Summarize a claim for the queue."""
    claim = claim_from(row)
    return {
        **{key: claim[key] for key in QUEUE_FIELDS},
        "customer_name": row["customer_name"],
    }


def find_claim(db: Connection, claim_id: str) -> dict[str, Any]:
    """Return a claim, or 404 if there's no such claim."""
    row = db.execute("SELECT * FROM claims WHERE claim_id = ?", (claim_id,)).fetchone()
    if row is None:
        raise HTTPException(404, f"There is no claim {claim_id}.")
    return claim_from(row)


def find_record(db: Connection, kind: str, record_id: str) -> dict[str, Any]:
    """Return a policy, customer or handler, or 404 if there's no such record."""
    row = db.execute(RECORD_QUERIES[kind], (record_id,)).fetchone()
    if row is None:
        raise HTTPException(404, f"There is no {kind} {record_id}.")
    return json.loads(row["record"])


@app.get("/api/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the backend is running."""
    return {"status": "ok"}


@app.get("/api/claims", operation_id="list_claims")
def list_claims() -> list[dict[str, Any]]:
    """List the claims in the queue, with where each one stands."""
    with transaction() as db:
        rows = db.execute(
            "SELECT claims.*, json_extract(customers.record, '$.name') AS customer_name"
            " FROM claims JOIN customers"
            " ON customers.customer_id = json_extract(claims.record, '$.customer_id')"
            " ORDER BY claim_id"
        ).fetchall()
    return [queue_entry(row) for row in rows]


@app.get("/api/claims/{claim_id}", operation_id="get_claim")
def get_claim(claim_id: str) -> dict[str, Any]:
    """Get a claim in full, with the decision, sign-off and payment."""
    with transaction() as db:
        return find_claim(db, claim_id)


@app.get("/api/policies/{policy_id}", operation_id="get_policy")
def get_policy(policy_id: str) -> dict[str, Any]:
    """Get a policy, with its plan's limits and the details of its add-ons."""
    with transaction() as db:
        policy = find_record(db, "policy", policy_id)
    plans = reference("plans.json")
    return {
        **policy,
        "plan_details": next(
            plan for plan in plans["plans"] if plan["plan"] == policy["plan"]
        ),
        "add_on_details": [
            add_on
            for add_on in plans["add_ons"]
            if add_on["add_on"] in policy["add_ons"]
        ],
    }


@app.get("/api/customers/{customer_id}", operation_id="get_customer")
def get_customer(customer_id: str) -> dict[str, Any]:
    """Get a customer, with their claim history."""
    with transaction() as db:
        return find_record(db, "customer", customer_id)


@app.get("/api/handlers", operation_id="list_handlers")
def list_handlers() -> list[dict[str, Any]]:
    """List the claims handlers."""
    with transaction() as db:
        rows = db.execute("SELECT record FROM handlers ORDER BY handler_id").fetchall()
    return [json.loads(row["record"]) for row in rows]


@app.get("/api/policy-wording", operation_id="get_policy_wording")
def get_policy_wording() -> dict[str, str]:
    """Get the policy wording that decisions follow."""
    return {
        "version": reference("company.json")["policy_wording_version"],
        "text": (DATA / "policy_wording.md").read_text(encoding="utf-8"),
    }
