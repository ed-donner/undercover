"""Deterministic guardrails for recommendation content and context."""

import re
from typing import Any

from agent.models import Recommendation

UNSUPPORTED_ACTION_CLAIM = re.compile(
    r"\b(?:i|we|shoppie)\s+(?:have\s+)?"
    r"(?:cancelled|canceled|refunded|replaced|returned|processed|sent)\b"
    r"|\b(?:order|refund|cancellation|return|replacement)\s+"
    r"(?:has been|was|is now|has)\s+(?:successfully\s+)?"
    r"(?:cancelled|canceled|refunded|replaced|returned|processed|issued|sent|completed)\b"
    r"|\b(?:refund|replacement|cancellation|return)\s+"
    r"(?:is complete|is completed)\b",
    re.IGNORECASE,
)
FOOD_SAFETY_TERMS = (
    "food safety",
    "allergy",
    "allergic",
    "spoiled",
    "spoilage",
    "unsafe",
    "contamination",
    "warm when",
    "smells sour",
)
MIN_ITEMS_FOR_SCOPE_AMBIGUITY = 2
MIN_ITEM_NAME_TERMS_TO_MATCH = 2
GENERIC_ITEM_TERMS = {"the", "set", "of", "and", "for", "pack"}


def contains_unsupported_execution_claim(recommendation: Recommendation) -> bool:
    """Detect language that says an external action already happened."""
    content = " ".join(
        [
            recommendation.rationale,
            recommendation.next_action,
            *recommendation.policy_citations,
        ]
    )
    return UNSUPPORTED_ACTION_CLAIM.search(content) is not None


def apply_context_overrides(
    context: dict[str, Any], recommendation: Recommendation
) -> Recommendation:
    """Hold ambiguous cancellations and food-safety cases for support review."""
    result = recommendation.model_copy(deep=True)
    request = context["request"]
    order = context["order"]
    message = request["customer_message"].casefold()
    evidence = " ".join(
        item.get("description", "") for item in request.get("evidence", [])
    ).casefold()
    if any(term in f"{message} {evidence}" for term in FOOD_SAFETY_TERMS):
        result.priority_human_review = True
        result.rationale = (
            "A food-safety concern requires prompt support review. " + result.rationale
        )
        result.next_action = (
            "Escalate to a support agent promptly; do not consume or return the item. "
            + result.next_action
        )
        result.policy_citations = unique_citations(
            result.policy_citations,
            "Returns Policy: Food safety or allergy concern",
        )
    elif request["type"] == "cancellation" and has_scope_ambiguity(request, order):
        result.outcome = "request_information"
        result.rationale = (
            "The customer identifies a specific item but asks to cancel the whole "
            "order. A support agent should confirm the intended scope."
        )
        result.next_action = (
            "Ask the customer to confirm which item or order they want cancelled."
        )
        result.policy_citations = unique_citations(
            result.policy_citations,
            "Cancellation Policy: Customer-requested cancellations",
        )
    return result


def has_scope_ambiguity(request: dict[str, Any], order: dict[str, Any]) -> bool:
    """Identify a specific product named inside a whole-order cancellation."""
    if (
        request["requested_scope"] != "whole_order"
        or len(order["items"]) < MIN_ITEMS_FOR_SCOPE_AMBIGUITY
    ):
        return False
    message_terms = set(
        re.findall(r"[a-z0-9]+", request["customer_message"].casefold())
    )
    return any(
        len(item_terms(item["name"]) & message_terms) >= MIN_ITEM_NAME_TERMS_TO_MATCH
        for item in order["items"]
    )


def item_terms(name: str) -> set[str]:
    """Return meaningful product-name words for ambiguity checks."""
    return set(re.findall(r"[a-z0-9]+", name.casefold())) - GENERIC_ITEM_TERMS


def unique_citations(citations: list[str], required: str) -> list[str]:
    """Add a required safety citation only once."""
    if required in citations:
        return citations
    return [*citations, required]
