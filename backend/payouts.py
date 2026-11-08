"""UnderCover's payout rules for an approved claim.

The rules come from section 10 of the policy wording, the plan limits in
data/plans.json and sections 6, 7 and 10 of the claims manual.
"""

from decimal import Decimal
from math import ceil
from typing import Any, Literal

from pydantic import BaseModel, Field

from backend import data, money
from backend.money import Amount

CASH_LIMIT = Decimal(100)
HOTEL_NIGHT_LIMIT = Decimal(350)
MEALS_PER_TRAVELER_PER_DAY = Decimal(35)

Benefit = Literal[
    "trip_cancellation",
    "trip_interruption",
    "trip_delay",
    "baggage_delay",
    "baggage",
    "passport",
    "emergency_medical",
]

BENEFIT_MAXIMUM = {
    "trip_cancellation": "trip_cancellation_max",
    "trip_interruption": "trip_cancellation_max",
    "trip_delay": "trip_delay_max",
    "baggage_delay": "baggage_delay_max",
    "baggage": "baggage_max",
    "passport": "passport_max",
    "emergency_medical": "emergency_medical_max",
}


class Line(BaseModel):
    """One covered item or expense on a claim."""

    description: str
    amount: Amount
    quantity: int = Field(ge=1)
    kind: Literal[
        "item", "electronics", "cash", "expense", "hotel", "meals_without_receipts"
    ]
    nights: int = Field(ge=0)
    hours: int = Field(ge=0)


def needs_sign_off(payout: Decimal) -> bool:
    """Say whether a payout is over the limit that needs a handler's sign-off."""
    return payout > data.PAYOUT_APPROVAL_LIMIT


def _step(description: str, amount: Decimal) -> dict[str, Any]:
    return {"step": description, "amount": money.dollars(amount)}


def _limit(line: Line, policy: dict[str, Any]) -> Decimal | None:
    """Return the most paid for one line, or None when it has no limit of its own."""
    plan = data.PLANS[policy["plan"]]
    travelers = len(policy["travelers"])
    match line.kind:
        case "item":
            return plan["per_item_limit"] * line.quantity
        case "electronics":
            plus = data.ADD_ONS["electronics_plus"]["electronics_per_item_limit"]
            has_plus = "electronics_plus" in policy["add_ons"]
            return (plus if has_plus else plan["per_item_limit"]) * line.quantity
        case "hotel":
            return HOTEL_NIGHT_LIMIT * ceil(travelers / 2) * line.nights
        case "meals_without_receipts":
            return MEALS_PER_TRAVELER_PER_DAY * travelers * ceil(line.hours / 24)
        case _:
            return None


def _eligible(line: Line, policy: dict[str, Any]) -> dict[str, Any]:
    limit = _limit(line, policy)
    if limit is not None and line.amount > limit:
        return _step(f"{line.description}, limited to ${limit:,.2f}", limit)
    return _step(line.description, line.amount)


def _benefit_maximum(policy: dict[str, Any], benefit: Benefit) -> Decimal:
    maximum = data.PLANS[policy["plan"]][BENEFIT_MAXIMUM[benefit]]
    if benefit in ("trip_cancellation", "trip_interruption"):
        return min(maximum, policy["trip"]["trip_cost"])
    return maximum


def work_out_payout(
    policy_id: str,
    benefit: Benefit,
    lines: list[Line],
    paid_by_others: Decimal,
) -> dict[str, Any]:
    """Work out the payout on an approved claim, following section 10 of the wording."""
    policy = data.POLICIES[policy_id]
    calculation = [_eligible(i, policy) for i in lines if i.kind != "cash"]
    cash = sum((i.amount for i in lines if i.kind == "cash"), Decimal(0))
    if cash:
        calculation.append(
            _step(f"Cash, up to ${CASH_LIMIT:,.0f} in all", min(cash, CASH_LIMIT))
        )
    total = sum((entry["amount"] for entry in calculation), Decimal(0))

    if paid_by_others:
        calculation.append(
            _step("Less what others have paid or refunded", -paid_by_others)
        )
        total -= paid_by_others

    if benefit in data.DEDUCTIBLE_BENEFITS and total > 0:
        deductible = min(data.PLANS[policy["plan"]]["deductible"], total)
        if deductible:
            calculation.append(_step("Less the deductible", -deductible))
            total -= deductible

    maximum = _benefit_maximum(policy, benefit)
    if total > maximum:
        calculation.append(
            _step(
                f"Less the amount over the maximum of ${maximum:,.0f}", maximum - total
            )
        )
        total = maximum

    if total < 0:
        calculation.append(_step("Nothing is left to pay", -total))
        total = Decimal(0)

    payout = money.dollars(total)
    return {
        "calculation": calculation,
        "payout": payout,
        "needs_sign_off": needs_sign_off(payout),
    }
