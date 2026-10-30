"""Money: `Decimal` dollars in Python and on the wire, whole cents in SQLite."""

from decimal import Decimal
from typing import Annotated, Any

from pydantic import Field

CENT = Decimal("0.01")

Amount = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]

MONEY_KEYS = {
    "amount",
    "amount_claimed",
    "amount_paid",
    "trip_cost",
    "payout_approval_limit",
    "baggage_delay_max",
    "baggage_max",
    "deductible",
    "electronics_per_item_limit",
    "emergency_medical_max",
    "passport_max",
    "per_item_limit",
    "trip_cancellation_max",
    "trip_delay_max",
}


def dollars(value: Any) -> Decimal:
    """Return a number as dollars, to the cent."""
    return Decimal(str(value)).quantize(CENT)


def to_cents(amount: Decimal) -> int:
    """Return an amount in whole cents."""
    return int(amount * 100)


def from_cents(cents: int) -> Decimal:
    """Return whole cents as dollars."""
    return dollars(Decimal(cents) / 100)


def convert(value: Any) -> Any:
    """Turn every money field in loaded JSON into `Decimal` dollars."""
    if isinstance(value, dict):
        return {
            key: dollars(item) if key in MONEY_KEYS else convert(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [convert(item) for item in value]
    return value
