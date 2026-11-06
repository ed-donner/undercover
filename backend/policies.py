"""Select the Shoppie policy needed for a support request."""

from pathlib import Path

POLICY_DIRECTORY = Path(__file__).resolve().parent.parent / "docs"
POLICY_FILES = {
    "cancellation": "cancellation-policy.md",
    "return": "returns-policy.md",
    "return_or_refund": "returns-policy.md",
    "replacement_or_refund": "returns-policy.md",
    "missing_item": "returns-policy.md",
    "order_question": "shopping-policy.md",
    "delivery_question": "shopping-policy.md",
    "product_question": "shopping-policy.md",
}


def policy_for_request_type(request_type: str) -> dict[str, str]:
    """Return the applicable sample policy for a request type."""
    file_name = POLICY_FILES[request_type]
    return {
        "name": file_name.removesuffix(".md").replace("-", " ").title(),
        "content": (POLICY_DIRECTORY / file_name).read_text(encoding="utf-8"),
    }
