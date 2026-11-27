"""The UnderCover backend."""

import json
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException

from backend import db
from backend.models import Claim, ClaimSummary, Customer, Handler, Policy, Text


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
    return Claim.model_validate(
        load_claim(connection, claim_id)
        | {"decision": None, "payment": None, "sign_off": None}
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
