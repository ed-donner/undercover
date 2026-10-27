"""UnderCover's reference data: read-only, loaded once from data/."""

import json
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _load_json(name: str) -> Any:
    return json.loads((DATA_DIR / name).read_text())


COMPANY: dict[str, Any] = _load_json("company.json")
PAYOUT_APPROVAL_LIMIT: float = COMPANY["payout_approval_limit"]

PLANS: dict[str, Any] = {
    plan["plan"]: plan for plan in _load_json("plans.json")["plans"]
}
POLICIES: dict[str, Any] = {
    policy["policy_id"]: policy for policy in _load_json("policies.json")
}
CUSTOMERS: dict[str, Any] = {
    customer["customer_id"]: customer for customer in _load_json("customers.json")
}
HANDLERS: list[dict[str, Any]] = _load_json("handlers.json")
CLAIMS: dict[str, Any] = {
    claim["claim_id"]: claim for claim in _load_json("claims.json")
}

POLICY_WORDING: str = (DATA_DIR / "policy_wording.md").read_text()

CLAIM_IDS_BY_SUBMITTED_ON: list[str] = [
    claim["claim_id"]
    for claim in sorted(CLAIMS.values(), key=lambda c: c["submitted_on"])
]


def handler(handler_id: str) -> dict[str, Any] | None:
    """Return the handler with this id, or None."""
    return next((h for h in HANDLERS if h["handler_id"] == handler_id), None)
