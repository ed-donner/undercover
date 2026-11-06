"""Structured data returned by the Shoppie Agent."""

from typing import Literal

from pydantic import BaseModel


class Recommendation(BaseModel):
    """Structured recommendation for a support agent to review."""

    outcome: Literal["approve", "decline", "request_information"]
    rationale: str
    policy_citations: list[str]
    next_action: str
    priority_human_review: bool
