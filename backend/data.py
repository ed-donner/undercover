"""UnderCover's reference data: read-only, loaded once from data/."""

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from backend import money

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _load_json(name: str) -> Any:
    text = (DATA_DIR / name).read_text()
    return money.convert(json.loads(text, parse_float=Decimal))


_PLAN_DATA = _load_json("plans.json")
PLANS: dict[str, Any] = {plan["plan"]: plan for plan in _PLAN_DATA["plans"]}
ADD_ONS: dict[str, Any] = {a["add_on"]: a for a in _PLAN_DATA["add_ons"]}
DEDUCTIBLE_BENEFITS: list[str] = _PLAN_DATA["deductible_applies_to"]
POLICIES: dict[str, Any] = {
    policy["policy_id"]: policy for policy in _load_json("policies.json")
}
CUSTOMERS: dict[str, Any] = {
    customer["customer_id"]: customer for customer in _load_json("customers.json")
}
CLAIMS: dict[str, Any] = {
    claim["claim_id"]: claim for claim in _load_json("claims.json")
}

CLAIM_IDS_BY_SUBMITTED_ON: list[str] = [
    claim["claim_id"]
    for claim in sorted(CLAIMS.values(), key=lambda c: c["submitted_on"])
]
