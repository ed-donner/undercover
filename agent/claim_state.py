"""What the claim graph keeps for one claim, saved after every step."""

from typing import Annotated, TypedDict

from langchain_core.messages import HumanMessage
from langgraph.graph.message import add_messages


class ClaimState(TypedDict):
    """The conversation, the decision once there is one, and the model calls so far."""

    messages: Annotated[list, add_messages]
    decision: str
    payout: str
    needs_sign_off: bool
    model_calls: int


def new_claim(claim_id: str) -> ClaimState:
    """Return the state a claim starts with."""
    return {
        "messages": [HumanMessage(f"Decide claim {claim_id}.")],
        "decision": "",
        "payout": "",
        "needs_sign_off": False,
        "model_calls": 0,
    }
