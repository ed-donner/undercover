"""UnderCover's reference data: read-only, loaded once from data/."""

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from backend import money
from backend.errors import NotFound

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _load_json(name: str) -> Any:
    text = (DATA_DIR / name).read_text()
    return money.convert(json.loads(text, parse_float=Decimal))


COMPANY: dict[str, Any] = _load_json("company.json")
PAYOUT_APPROVAL_LIMIT: Decimal = COMPANY["payout_approval_limit"]

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
CLAIMS_MANUAL: str = (DATA_DIR / "claims_manual.md").read_text()


def _sections(text: str) -> dict[str, str]:
    """Split a Markdown document into its ``##``-headed sections, in order."""
    sections: dict[str, str] = {}
    heading: str | None = None
    lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            if heading is not None:
                sections[heading] = "\n".join(lines).strip()
            heading, lines = line.removeprefix("## ").strip(), []
        elif heading is not None:
            lines.append(line)
    if heading is not None:
        sections[heading] = "\n".join(lines).strip()
    return sections


DOCUMENTS: dict[str, dict[str, str]] = {
    "policy_wording": _sections(POLICY_WORDING),
    "claims_manual": _sections(CLAIMS_MANUAL),
}

CLAIM_IDS_BY_SUBMITTED_ON: list[str] = [
    claim["claim_id"]
    for claim in sorted(CLAIMS.values(), key=lambda c: c["submitted_on"])
]


def handler(handler_id: str) -> dict[str, Any] | None:
    """Return the handler with this id, or None."""
    return next((h for h in HANDLERS if h["handler_id"] == handler_id), None)


def get_document(name: str) -> dict[str, str]:
    """Return a document's sections by heading, or raise NotFound."""
    if name not in DOCUMENTS:
        raise NotFound(f"No document {name}")
    return DOCUMENTS[name]


def get_section(document: str, heading: str) -> str:
    """Return one section's text, or raise NotFound."""
    sections = get_document(document)
    if heading not in sections:
        raise NotFound(f"No section {heading}")
    return sections[heading]
