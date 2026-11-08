"""The nodes of the claim graph: each takes the state and returns what it changes."""

from decimal import Decimal
from typing import Any

from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from langgraph.runtime import Runtime
from langgraph.types import interrupt

from agent import api
from agent.claim_state import ClaimState
from agent.tools import ClaimContext

MAX_MODEL_CALLS = 30
WAITING_FOR_SIGN_OFF = "waiting for sign-off"


class ModelCallLimit(Exception):  # noqa: N818 - a failure of the claim
    """The model was called more times than a claim should ever need."""


def agent(
    state: ClaimState,
    *,
    model: Runnable[LanguageModelInput, AIMessage],
    instructions: str,
) -> dict[str, Any]:
    """Call the model with the conversation so far."""
    if state["model_calls"] >= MAX_MODEL_CALLS:
        raise ModelCallLimit(f"More than {MAX_MODEL_CALLS} model calls on one claim")
    reply = model.invoke([SystemMessage(instructions), *state["messages"]])
    return {"messages": [reply], "model_calls": state["model_calls"] + 1}


def settle(state: ClaimState, runtime: Runtime[ClaimContext]) -> dict[str, Any]:
    """Read the decision back from the backend, which says if it needs a sign-off."""
    claim_id = runtime.context.claim_id
    claim = api.get_claim(claim_id)
    if claim["decision"] is None:
        reminder = HumanMessage(
            "No decision is recorded yet. Record it with decide_claim."
        )
        return {"messages": [reminder], "decision": ""}
    needs_sign_off = claim["status"] == WAITING_FOR_SIGN_OFF
    if needs_sign_off:
        api.record_step(
            claim_id, f"Waiting for a handler to sign off ${claim['payout']}"
        )
    return {
        "decision": claim["decision"],
        "payout": claim["payout"],
        "needs_sign_off": needs_sign_off,
    }


def approval(state: ClaimState, runtime: Runtime[ClaimContext]) -> dict[str, Any]:
    """Wait for a handler's sign-off. Anything before `interrupt` runs twice."""
    answer = interrupt(
        {"claim_id": runtime.context.claim_id, "payout": state["payout"]}
    )
    api.record_step(runtime.context.claim_id, f"Signed off by {answer['handler']}")
    return {}


def pay(state: ClaimState, runtime: Runtime[ClaimContext]) -> dict[str, Any]:
    """Pay the claim; the backend treats a repeat as done."""
    claim_id = runtime.context.claim_id
    api.pay_claim(claim_id, Decimal(state["payout"]))
    api.record_step(claim_id, f"Paid ${state['payout']}")
    return {}
