"""The agent's only way to the UnderCover backend.

One client, and one function for each operation the agents use.
"""

from decimal import Decimal
from http import HTTPStatus
from typing import Annotated, Any, Literal

import httpx
from pydantic import BaseModel, Field

BACKEND_URL = "http://localhost:8000"

Document = Literal["policy_wording", "claims_manual"]
Decision = Literal["approve", "decline", "refer"]
Amount = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
Benefit = Literal[
    "trip_cancellation",
    "trip_interruption",
    "trip_delay",
    "baggage_delay",
    "baggage",
    "passport",
    "emergency_medical",
]
WAITING = "waiting"
WAITING_FOR_SIGN_OFF = "waiting for sign-off"
RunItemStatus = Literal["to do", "in progress", "done", "left for a handler"]


class Line(BaseModel):
    """One covered item or expense on a claim."""

    description: str = Field(description="What the item or expense is")
    amount: Amount = Field(
        description="The total claimed for the line in US dollars, before any limits. "
        "For several items, the total for all of them"
    )
    quantity: int = Field(
        default=1,
        ge=1,
        description="How many separate items the line holds, such as 3 for three "
        "shirts. A pair or a set is one item",
    )
    kind: Literal[
        "item", "electronics", "cash", "expense", "hotel", "meals_without_receipts"
    ] = Field(
        description="item: a belonging, or a pair or set that counts as one item. "
        "electronics: only a phone, tablet, laptop, camera or its lens, e-reader or "
        "smartwatch; any other device is an item. "
        "cash: cash that was lost or stolen. "
        "expense: any other cost with a receipt, such as a medical bill, a meal, a "
        "taxi, a fee or a prepaid trip cost. "
        "hotel: a hotel during a trip delay. "
        "meals_without_receipts: meals during a trip delay with no receipts."
    )
    nights: int = Field(default=0, description="For a hotel, the number of nights")
    hours: int = Field(
        default=0,
        description="For meals without receipts, the length of the delay in hours",
    )


client = httpx.Client(base_url=BACKEND_URL, timeout=10)


class ApiRefusal(Exception):  # noqa: N818 - a refusal, not a failure
    """The backend refused a request; the message says why, for the model to read."""


def _call(method: str, path: str, **kwargs: Any) -> Any:
    response = client.request(method, path, **kwargs)
    if response.is_client_error:
        detail = response.json().get("detail", response.text)
        raise ApiRefusal(f"{response.status_code}: {detail}")
    response.raise_for_status()
    return response.json()


def claim_instructions() -> str:
    """Return the instructions for deciding one claim."""
    return _call("GET", "/api/claim-instructions")["instructions"]


def queue_instructions() -> str:
    """Return the instructions for running the claims queue."""
    return _call("GET", "/api/queue-instructions")["instructions"]


def list_claims() -> list[dict[str, Any]]:
    """List every claim in the queue, oldest submitted first."""
    return _call("GET", "/api/claims")


def get_claim(claim_id: str) -> dict[str, Any]:
    """Return one claim in full, with its policy and the customer's claim history."""
    return _call("GET", f"/api/claims/{claim_id}")


def list_sections(document: Document) -> list[str]:
    """List a document's section headings."""
    return _call("GET", f"/api/documents/{document}/sections")


def get_section(document: Document, heading: str) -> str:
    """Return the text of one section of a document."""
    params = {"heading": heading}
    return _call("GET", f"/api/documents/{document}/section", params=params)["text"]


def record_step(claim_id: str, text: str) -> None:
    """Record one step of the agent's work on a claim."""
    _call("POST", f"/api/claims/{claim_id}/steps", json={"text": text})


def decide_claim(
    claim_id: str,
    decision: Decision,
    payout: Amount,
    reason: str,
    policy_reference: str,
) -> dict[str, Any]:
    """Record the decision on a claim, and return the claim."""
    body = {
        "decision": decision,
        "payout": str(payout),
        "reason": reason,
        "policy_reference": policy_reference,
    }
    return _call("POST", f"/api/claims/{claim_id}/decision", json=body)


def pay_claim(claim_id: str, amount: Amount) -> dict[str, Any]:
    """Pay a claim its approved payout, and return the claim."""
    body = {"amount": str(amount)}
    return _call("POST", f"/api/claims/{claim_id}/payment", json=body)


def list_unfinished_claims() -> list[str]:
    """List the claims the agent must carry on with."""
    return _call("GET", "/api/unfinished-claims")


def calculate_payout(
    policy_id: str, benefit: Benefit, lines: list[Line], paid_by_others: Amount
) -> dict[str, Any]:
    """Work out a payout with UnderCover's payout rules."""
    body = {
        "policy_id": policy_id,
        "benefit": benefit,
        "lines": [line.model_dump(mode="json") for line in lines],
        "paid_by_others": str(paid_by_others),
    }
    return _call("POST", "/api/payouts", json=body)


def requeue_claim(claim_id: str) -> None:
    """Put a stuck claim back in the queue as waiting."""
    _call("POST", f"/api/claims/{claim_id}/requeue")


def start_run(claim_ids: list[str]) -> int:
    """Start a run with one to-do item per claim, and return its id."""
    return _call("POST", "/api/runs", json={"claim_ids": claim_ids})["run_id"]


def get_current_run() -> dict[str, Any]:
    """Return the most recently started run, with its to-do items."""
    return _call("GET", "/api/runs/current")


def get_unfinished_run() -> dict[str, Any] | None:
    """Return the most recently started run, unless it has finished or there is none."""
    run = _call("GET", "/api/runs/current")
    return None if run is None or run["finished_on"] else run


def update_run_item(
    run_id: int, claim_id: str, status: RunItemStatus, note: str
) -> None:
    """Set a to-do item's status and note."""
    body = {"status": status, "note": note}
    _call("POST", f"/api/runs/{run_id}/items/{claim_id}", json=body)


def finish_run(run_id: int, summary: str) -> str | None:
    """Finish a run; if items are still unsettled, return what is outstanding."""
    response = client.post(f"/api/runs/{run_id}/finish", json={"summary": summary})
    if response.status_code == HTTPStatus.CONFLICT:
        return response.json()["detail"]
    response.raise_for_status()
    return None
