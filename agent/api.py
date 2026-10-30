"""The agent's only way to the UnderCover backend.

One client, and one function for each operation the agents use.
"""

from decimal import Decimal
from http import HTTPStatus
from typing import Annotated, Any, Literal

import httpx
from pydantic import Field

BACKEND_URL = "http://localhost:8000"

Document = Literal["policy_wording", "claims_manual"]
Decision = Literal["approve", "decline", "refer"]
Amount = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
RunItemStatus = Literal["to do", "in progress", "done", "left for a handler"]

client = httpx.Client(base_url=BACKEND_URL, timeout=10)


def _call(method: str, path: str, **kwargs: Any) -> Any:
    response = client.request(method, path, **kwargs)
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
) -> None:
    """Record the decision on a claim."""
    body = {
        "decision": decision,
        "payout": str(payout),
        "reason": reason,
        "policy_reference": policy_reference,
    }
    _call("POST", f"/api/claims/{claim_id}/decision", json=body)


def requeue_claim(claim_id: str) -> None:
    """Put a stuck claim back in the queue as waiting."""
    _call("POST", f"/api/claims/{claim_id}/requeue")


def start_run(claim_ids: list[str]) -> int:
    """Start a run with one to-do item per claim, and return its id."""
    return _call("POST", "/api/runs", json={"claim_ids": claim_ids})["run_id"]


def get_current_run() -> dict[str, Any]:
    """Return the most recently started run, with its to-do items."""
    return _call("GET", "/api/runs/current")


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
