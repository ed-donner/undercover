"""The UnderCover backend."""

from typing import Any

from fastapi import FastAPI, HTTPException

from backend import db
from backend.data import (
    CLAIM_IDS_BY_SUBMITTED_ON,
    CLAIMS,
    CUSTOMERS,
    POLICIES,
    POLICY_WORDING,
)

app = FastAPI(title="UnderCover")


@app.get("/api/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the backend is running."""
    return {"status": "ok"}


def _claim_row(claim_id: str) -> dict[str, Any]:
    conn = db.connect()
    row = conn.execute(
        "SELECT * FROM claims WHERE claim_id = ?", (claim_id,)
    ).fetchone()
    conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail=f"No claim {claim_id}")
    return dict(row)


@app.get("/api/claims", operation_id="list_claims")
def list_claims() -> list[dict[str, Any]]:
    """List every claim in the queue, oldest submitted first."""
    conn = db.connect()
    statuses = {
        row["claim_id"]: row["status"]
        for row in conn.execute("SELECT claim_id, status FROM claims")
    }
    conn.close()
    return [
        {
            "claim_id": claim_id,
            "claim_type": CLAIMS[claim_id]["claim_type"],
            "summary": CLAIMS[claim_id]["summary"],
            "amount_claimed": CLAIMS[claim_id]["amount_claimed"],
            "status": statuses[claim_id],
        }
        for claim_id in CLAIM_IDS_BY_SUBMITTED_ON
    ]


@app.get("/api/claims/{claim_id}", operation_id="get_claim")
def get_claim(claim_id: str) -> dict[str, Any]:
    """Return one claim in full, with its policy and its customer's claim history."""
    if claim_id not in CLAIMS:
        raise HTTPException(status_code=404, detail=f"No claim {claim_id}")
    claim = {k: v for k, v in CLAIMS[claim_id].items() if k != "status"}
    row = _claim_row(claim_id)
    policy = POLICIES[claim["policy_id"]]
    customer = CUSTOMERS[claim["customer_id"]]
    return {
        **claim,
        **row,
        "policy": policy,
        "customer_previous_claims": customer["previous_claims"],
    }


@app.get("/api/policy-wording", operation_id="get_policy_wording")
def get_policy_wording() -> dict[str, str]:
    """Return the full text of UnderCover's policy wording."""
    return {"policy_wording": POLICY_WORDING}
