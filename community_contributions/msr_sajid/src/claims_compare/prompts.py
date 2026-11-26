"""The decision schema and the prompts shared by both approaches."""

import json
from typing import Literal

from pydantic import BaseModel, Field

INSTRUCTIONS = (
    "You are a claims handler at a small travel insurer. Decide the claim you are given, "
    "using the policy wording below. Choose approve, decline or refer, and work out the payout."
)


class ClaimDecision(BaseModel):
    """One decision on one claim. The rationale comes first so the model reasons before it decides."""

    rationale: str = Field(description="2-3 sentences, citing the policy section")
    decision: Literal["approve", "decline", "refer"]
    payout: float = Field(description="US dollars to pay, or 0 for a decline or a referral")


def system_prompt(wording: str, with_tools: bool = False) -> str:
    tools = "\nUse your tools to look up the policy record and to record your decision.\n" if with_tools else ""
    return f"{INSTRUCTIONS}{tools}\n\n{wording}"


def claim_prompt(claim: dict, policy: dict | None = None) -> str:
    """The claim as JSON. The single call also gets the policy record; the agent fetches its own."""
    parts = []
    if policy is not None:
        parts.append(f"# Policy record\n\n{json.dumps(policy, indent=2)}")
    parts.append(f"# Claim\n\n{json.dumps(claim, indent=2)}")
    return "\n\n".join(parts)
