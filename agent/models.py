"""Structured data returned by the Shoppie Agent."""

from typing import Literal

from pydantic import BaseModel


class Recommendation(BaseModel):
    """Final structured recommendation returned by the Shoppie Agent."""

    outcome: Literal["approve", "decline", "request_information"]
    rationale: str
    policy_citations: list[str]
    next_action: str
    priority_human_review: bool


class TodoItem(BaseModel):
    """One item on the queue agent's to-do list."""

    request_id: str
    title: str
    status: Literal["to_do", "in_progress", "done", "left_for_support"]
