"""The UnderCover backend."""

from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel

from agent.main import run as agent_run
from backend import data, db
from backend.data import (
    CLAIM_IDS_BY_SUBMITTED_ON,
    CLAIMS,
    CUSTOMERS,
    HANDLERS,
    PAYOUT_APPROVAL_LIMIT,
    POLICIES,
    POLICY_WORDING,
)
from backend.instructions import AGENT_INSTRUCTIONS

app = FastAPI(title="UnderCover")


class Decision(BaseModel):
    decision: Literal["approve", "decline", "refer"]
    payout: float
    reason: str
    policy_reference: str


class Step(BaseModel):
    text: str


class SignOff(BaseModel):
    handler_id: str


class Payment(BaseModel):
    amount: float


def _now() -> str:
    return datetime.now(UTC).isoformat()


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


@app.get("/api/documents/{document}/sections", operation_id="list_sections")
def list_sections(document: str) -> list[str]:
    """List a document's section headings, in order."""
    sections = data.DOCUMENTS.get(document)
    if sections is None:
        raise HTTPException(status_code=404, detail=f"No document {document}")
    return list(sections)


@app.get("/api/documents/{document}/section", operation_id="get_section")
def get_section(document: str, heading: str) -> dict[str, str]:
    """Return the text of one section of a document."""
    sections = data.DOCUMENTS.get(document)
    if sections is None:
        raise HTTPException(status_code=404, detail=f"No document {document}")
    text = sections.get(heading)
    if text is None:
        raise HTTPException(status_code=404, detail=f"No section {heading}")
    return {"text": text}


@app.get("/api/agent-instructions", operation_id="get_agent_instructions")
def get_agent_instructions() -> dict[str, str]:
    """Return the UnderCover Agent's instructions, read only."""
    return {"instructions": AGENT_INSTRUCTIONS}


@app.get("/api/handlers", operation_id="list_handlers")
def list_handlers() -> list[dict[str, Any]]:
    """List the claims handlers who can sign off an over-limit payout."""
    return [h for h in HANDLERS if h["can_approve_over_limit"]]


@app.post("/api/claims/{claim_id}/decision", operation_id="decide_claim")
def decide_claim(claim_id: str, decision: Decision) -> dict[str, Any]:
    """Record a decision on a claim, approve, decline or refer."""
    if claim_id not in CLAIMS:
        raise HTTPException(status_code=404, detail=f"No claim {claim_id}")
    over_limit = (
        decision.decision == "approve" and decision.payout > PAYOUT_APPROVAL_LIMIT
    )
    status = "waiting for sign-off" if over_limit else "decided"
    conn = db.connect()
    conn.execute(
        """UPDATE claims SET status = ?, decision = ?, payout = ?, reason = ?,
           policy_reference = ?, decided_on = ?, over_approval_limit = ?,
           signed_off_by = NULL, signed_off_on = NULL,
           paid_amount = NULL, paid_on = NULL
           WHERE claim_id = ?""",
        (
            status,
            decision.decision,
            decision.payout,
            decision.reason,
            decision.policy_reference,
            _now(),
            int(over_limit),
            claim_id,
        ),
    )
    conn.commit()
    conn.close()
    return _claim_row(claim_id)


@app.post("/api/claims/{claim_id}/steps", operation_id="record_step")
def record_step(claim_id: str, step: Step) -> dict[str, Any]:
    """Record one step of the agent's work on a claim."""
    if claim_id not in CLAIMS:
        raise HTTPException(status_code=404, detail=f"No claim {claim_id}")
    conn = db.connect()
    conn.execute(
        "INSERT INTO claim_steps (claim_id, recorded_on, text) VALUES (?, ?, ?)",
        (claim_id, _now(), step.text),
    )
    conn.execute(
        "UPDATE claims SET status = 'in progress' "
        "WHERE claim_id = ? AND status = 'waiting'",
        (claim_id,),
    )
    conn.commit()
    conn.close()
    return {"claim_id": claim_id, "text": step.text}


@app.get("/api/claims/{claim_id}/steps", operation_id="list_claim_steps")
def list_claim_steps(claim_id: str) -> list[dict[str, Any]]:
    """List a claim's steps, in the order they happened."""
    if claim_id not in CLAIMS:
        raise HTTPException(status_code=404, detail=f"No claim {claim_id}")
    conn = db.connect()
    rows = conn.execute(
        "SELECT recorded_on, text FROM claim_steps WHERE claim_id = ? ORDER BY id",
        (claim_id,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.post("/api/claims/{claim_id}/sign-off", operation_id="sign_off_claim")
def sign_off_claim(claim_id: str, sign_off: SignOff) -> dict[str, Any]:
    """Have a handler sign off an over-limit approved claim's payout."""
    row = _claim_row(claim_id)
    if row["status"] != "waiting for sign-off":
        raise HTTPException(status_code=409, detail="Claim is not waiting for sign-off")
    handler = data.handler(sign_off.handler_id)
    if handler is None or not handler["can_approve_over_limit"]:
        raise HTTPException(
            status_code=409, detail="This handler cannot sign off this claim"
        )
    conn = db.connect()
    conn.execute(
        """UPDATE claims SET status = 'decided', signed_off_by = ?, signed_off_on = ?
           WHERE claim_id = ?""",
        (sign_off.handler_id, _now(), claim_id),
    )
    conn.commit()
    conn.close()
    return _claim_row(claim_id)


@app.post("/api/claims/{claim_id}/payment", operation_id="pay_claim")
def pay_claim(claim_id: str, payment: Payment) -> dict[str, Any]:
    """Pay a claim's approved payout, blocked until any required sign-off is given."""
    row = _claim_row(claim_id)
    if row["decision"] != "approve":
        raise HTTPException(status_code=409, detail="Claim is not approved")
    if row["over_approval_limit"] and row["signed_off_by"] is None:
        raise HTTPException(
            status_code=409, detail="Claim needs a handler's sign-off before payment"
        )
    conn = db.connect()
    conn.execute(
        "UPDATE claims SET paid_amount = ?, paid_on = ? WHERE claim_id = ?",
        (payment.amount, _now(), claim_id),
    )
    conn.commit()
    conn.close()
    return _claim_row(claim_id)


@app.post("/api/claims/{claim_id}/run", operation_id="run_agent")
def run_agent(claim_id: str, background_tasks: BackgroundTasks) -> dict[str, Any]:
    """Schedule the UnderCover Agent to decide a waiting claim."""
    row = _claim_row(claim_id)
    if row["status"] != "waiting":
        raise HTTPException(status_code=409, detail="Claim is not waiting")
    conn = db.connect()
    conn.execute(
        "UPDATE claims SET status = 'in progress' WHERE claim_id = ?", (claim_id,)
    )
    conn.commit()
    conn.close()
    background_tasks.add_task(agent_run, claim_id, f"run-{claim_id}")
    return _claim_row(claim_id)
