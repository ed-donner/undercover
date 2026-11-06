"""The claim lifecycle: deciding, paying and signing off a claim."""

from datetime import UTC, datetime

from fastapi import HTTPException

from agent import main as agent
from backend import db
from backend.schemas import PaymentResult


def _now() -> str:
    return datetime.now(UTC).isoformat()


def run_claim(claim_id: str) -> str:
    """Run the agent on a claim and return its reply."""
    claim = db.require_claim(claim_id)
    if claim["status"] != "waiting":
        raise HTTPException(status_code=409, detail=f"Claim {claim_id} isn't waiting")

    db.update_claim(claim_id, status="in_progress")
    db.insert_event(claim_id, "run_claim", "Started working the claim", _now())
    return agent.run(claim_id, claim_id)


def decide_claim(
    claim_id: str, decision: str, payout: float, reason: str, reference: str
) -> None:
    """Record a decision on a claim: approve, decline or refer."""
    claim = db.require_claim(claim_id)
    if claim["status"] in ("decided", "waiting_for_sign_off"):
        raise HTTPException(
            status_code=409, detail=f"Claim {claim_id} is already decided"
        )

    status = claim["status"] if decision == "approve" else "decided"
    db.update_claim(
        claim_id,
        decision=decision,
        payout=payout,
        reason=reason,
        reference=reference,
        decided_at=_now(),
        status=status,
    )
    message = f"Decided to {decision}"
    if decision == "approve":
        message += f", payout ${payout:,.2f}"
    db.insert_event(claim_id, "decide_claim", message, _now())


def pay_claim(claim_id: str, amount: float) -> PaymentResult:
    """Pay an approved claim, or hold it for sign-off if it's over the limit."""
    claim = db.require_claim(claim_id)
    if claim["decision"] != "approve":
        raise HTTPException(
            status_code=400, detail=f"Claim {claim_id} was not approved"
        )
    if claim["paid_amount"] is not None:
        raise HTTPException(
            status_code=400, detail=f"Claim {claim_id} has already been paid"
        )

    limit = db.payout_approval_limit()
    if amount > limit and not claim["signed_off_by"]:
        db.update_claim(claim_id, status="waiting_for_sign_off")
        db.insert_event(
            claim_id,
            "pay_claim",
            f"Held for sign-off: payout ${amount:,.2f} is over the ${limit:,.0f} limit",
            _now(),
        )
        return PaymentResult(paid=False, status="waiting_for_sign_off")

    db.update_claim(claim_id, status="decided", paid_amount=amount, paid_at=_now())
    db.insert_event(claim_id, "pay_claim", f"Paid ${amount:,.2f}", _now())
    return PaymentResult(paid=True, status="decided")


def sign_off_claim(claim_id: str, handler_id: str) -> PaymentResult:
    """Sign off a claim that's waiting for a handler, then release its payment."""
    claim = db.require_claim(claim_id)
    if claim["status"] != "waiting_for_sign_off":
        raise HTTPException(
            status_code=409, detail=f"Claim {claim_id} isn't waiting for sign-off"
        )

    handler = db.fetch_handler(handler_id)
    if handler is None or not handler["can_approve_over_limit"]:
        raise HTTPException(
            status_code=400,
            detail=f"Handler {handler_id} can't sign off a claim over the limit",
        )

    db.update_claim(claim_id, signed_off_by=handler_id, signed_off_at=_now())
    db.insert_event(
        claim_id, "sign_off_claim", f"Signed off by {handler['name']}", _now()
    )
    return pay_claim(claim_id, claim["payout"])
