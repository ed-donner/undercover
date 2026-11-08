"""Shoppie's policy-backed refund calculation rules for a support request."""

from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field

FREE_DELIVERY_THRESHOLD = 499.0
STANDARD_DELIVERY_FEE = 49.0
RETURN_PICKUP_FEE = 75.0

RefundReason = Literal[
    "cancellation",
    "damaged_or_defective",
    "missing_item",
    "change_of_mind",
    "failed_delivery_customer",
    "failed_delivery_shoppie",
]
SHOPPIE_DELIVERY_REFUND_REASONS = {
    "cancellation",
    "damaged_or_defective",
    "missing_item",
    "failed_delivery_shoppie",
}
PICKUP_FEE_REASONS = {"change_of_mind", "failed_delivery_customer"}


class Line(BaseModel):
    """One covered order item and quantity to include in a refund calculation."""

    item_id: str = Field(description="The order item's item_id or sku")
    quantity: int = Field(
        ge=1, description="How many units of this item are covered by the refund"
    )


class RefundInput(BaseModel):
    """Inputs for calculating the eligible refund on a support request."""

    reason: RefundReason
    lines: list[Line] = Field(min_length=1)


class Step(TypedDict):
    """One line of the refund calculation."""

    step: str
    amount: float


class RefundCalculation(TypedDict):
    """The calculated refund breakdown and whether it requires support review."""

    calculation: list[Step]
    refund: float
    needs_sign_off: bool


def step(description: str, amount: float) -> Step:
    """Make one line of the calculation, rounded to the paisa."""
    return {"step": description, "amount": round(amount, 2)}


def find_order_item(order: dict[str, Any], identifier: str) -> dict[str, Any]:
    """Return the matching item from an order by item_id or sku, or raise ValueError."""
    for item in order["items"]:
        if identifier in {item.get("item_id"), item.get("sku")}:
            return item
    raise ValueError(f"Unknown order item: {identifier}")


def covered_quantities(
    order: dict[str, Any], lines: list[Line]
) -> dict[str, tuple[dict[str, Any], int]]:
    """Aggregate requested quantities per order item, capped at ordered quantities."""
    covered: dict[str, tuple[dict[str, Any], int]] = {}
    for line in lines:
        item = find_order_item(order, line.item_id)
        key = str(item.get("item_id") or item["sku"])
        existing_qty = covered[key][1] if key in covered else 0
        covered[key] = (item, min(int(item["quantity"]), existing_qty + line.quantity))
    return covered


def all_order_items_covered(
    order: dict[str, Any], covered: dict[str, tuple[dict[str, Any], int]]
) -> bool:
    """Report whether every unit of every item in the order is included."""
    for item in order["items"]:
        key = str(item.get("item_id") or item["sku"])
        if key not in covered or covered[key][1] < int(item["quantity"]):
            return False
    return True


def work_out_refund(
    order: dict[str, Any], reason: RefundReason, lines: list[Line]
) -> RefundCalculation:
    """Work out the eligible INR refund on a request under Shoppie's policies."""
    covered = covered_quantities(order, lines)
    calculation: list[Step] = []
    for item, quantity in covered.values():
        amount = min(
            float(item["line_total"]), round(float(item["unit_price"]) * quantity, 2)
        )
        calculation.append(step(f"{item['name']} (x{quantity})", amount))
    items_total = round(sum(entry["amount"] for entry in calculation), 2)
    total = items_total
    whole_order = all_order_items_covered(order, covered)
    delivery_fee = float(order.get("delivery_fee", 0.0))

    if whole_order and delivery_fee > 0 and reason in SHOPPIE_DELIVERY_REFUND_REASONS:
        calculation.append(step("Delivery fee refund", delivery_fee))
        total += delivery_fee
    elif (
        not whole_order
        and reason == "cancellation"
        and delivery_fee == 0
        and float(order["subtotal"]) >= FREE_DELIVERY_THRESHOLD
        and 0 < float(order["subtotal"]) - items_total < FREE_DELIVERY_THRESHOLD
    ):
        calculation.append(
            step(
                "Less standard delivery fee after partial cancellation",
                -STANDARD_DELIVERY_FEE,
            )
        )
        total -= STANDARD_DELIVERY_FEE

    if reason in PICKUP_FEE_REASONS and total > 0:
        calculation.append(
            step("Less return pickup or handling fee", -RETURN_PICKUP_FEE)
        )
        total -= RETURN_PICKUP_FEE

    if total < 0:
        calculation.append(step("Nothing is left to refund", -total))
        total = 0.0

    return {
        "calculation": calculation,
        "refund": round(total, 2),
        "needs_sign_off": True,
    }
