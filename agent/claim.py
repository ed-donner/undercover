"""The claim agent: a fresh agent for each claim, which decides it and reports back."""

import json
from collections.abc import Iterator
from typing import Any, Literal

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware, ModelCallLimitMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.tools import tool

from agent.common import api, call, instructions, retries

CALL_LIMIT = 25
STEP_LENGTH = 400
Document = Literal["policy-wording", "claims-manual"]


@tool
def get_claim(claim_id: str) -> str:
    """Get a claim in full: the story, the items claimed and the documents."""
    return call("GET", f"/api/claims/{claim_id}")


@tool
def get_policy(policy_id: str) -> str:
    """Get a policy with its plan's limits and the details of its add-ons."""
    return call("GET", f"/api/policies/{policy_id}")


@tool
def get_claim_history(customer_id: str) -> str:
    """Get a customer's earlier claims."""
    return call("GET", f"/api/customers/{customer_id}/history")


@tool
def list_sections(document: Document) -> str:
    """List the numbered sections of the policy wording or the claims manual."""
    return call("GET", f"/api/documents/{document}/sections")


@tool
def read_section(document: Document, number: str) -> str:
    """Read one numbered section of the policy wording or the claims manual."""
    return call("GET", f"/api/documents/{document}/sections/{number}")


@tool
def record_decision(
    claim_id: str,
    decision: Literal["approve", "decline", "refer"],
    payout: float,
    reason: str,
    policy_section: str,
) -> str:
    """Record the decision on a claim, with the payout, the reason and the section."""
    body = {
        "decision": decision,
        "payout": payout,
        "reason": reason,
        "policy_section": policy_section,
    }
    return call("POST", f"/api/claims/{claim_id}/decision", body)


@tool
def pay_claim(claim_id: str, amount: float) -> str:
    """Pay the approved payout on a claim."""
    return call("POST", f"/api/claims/{claim_id}/payment", {"amount": amount})


TOOLS = [
    get_claim,
    get_policy,
    get_claim_history,
    list_sections,
    read_section,
    record_decision,
    pay_claim,
]


def shorten(text: str) -> str:
    """Shorten long text for a step."""
    return text if len(text) <= STEP_LENGTH else text[:STEP_LENGTH] + "..."


def steps(message: BaseMessage) -> Iterator[tuple[str, str]]:
    """Describe a message from the claim agent as steps for the dashboard."""
    if isinstance(message, ToolMessage):
        yield "tool_result", f"{message.name}: {shorten(message.text)}"
        if message.name == "read_section" and not message.text.startswith("Refused"):
            section = json.loads(message.text)
            yield "read", f"{section['document']}, {section['section']}"
    elif isinstance(message, AIMessage):
        if message.text:
            yield "message", message.text
        for call_ in message.tool_calls:
            yield "tool_call", f"{call_['name']}({json.dumps(call_['args'])})"


def decide(claim_id: str, llm: BaseChatModel) -> None:
    """Let a fresh claim agent work a started claim, posting each step to the claim."""
    limit: AgentMiddleware[Any, Any, Any] = ModelCallLimitMiddleware(
        run_limit=CALL_LIMIT
    )
    agent = create_agent(
        llm,
        tools=TOOLS,
        system_prompt=instructions("claim"),
        middleware=[*retries(), limit],
    )
    for update in agent.stream(
        {"messages": [{"role": "user", "content": f"Please decide claim {claim_id}."}]},
        config={"recursion_limit": 4 * CALL_LIMIT},
        stream_mode="updates",
    ):
        for node in update.values():
            for message in (node or {}).get("messages", []):
                for kind, content in steps(message):
                    call(
                        "POST",
                        f"/api/claims/{claim_id}/steps",
                        {"kind": kind, "content": content},
                    )


def outcome(claim: dict[str, Any]) -> str:
    """Describe a decided claim in one line."""
    line = f"{claim['claim_id']}: {claim['decision']}"
    if claim["decision"] != "approve":
        return line
    if claim["paid_at"]:
        paid = "paid"
    elif claim["status"] == "awaiting_signoff":
        paid = "waiting for a handler's sign-off"
    else:
        paid = "not paid yet"
    return f"{line}, ${claim['payout']:,.2f}, {paid}"


def work_claim(claim_id: str, llm: BaseChatModel) -> str:
    """Work one waiting claim with a fresh claim agent and report the outcome in a line.

    It never raises: a claim that fails before it is decided is released, which puts
    it back in the queue or, on its second failure, leaves it for a handler.
    """
    started = call("POST", f"/api/claims/{claim_id}/start")
    if started.startswith("Refused"):
        return started
    try:
        decide(claim_id, llm)
        problem = "the agent finished without recording a decision"
    except Exception as error:
        problem = f"the agent stopped with an error: {error}"
    claim = api("GET", f"/api/claims/{claim_id}")
    if claim["status"] != "in_progress":
        return outcome(claim)
    claim = api(
        "POST", f"/api/claims/{claim_id}/release", {"problem": problem.capitalize()}
    )
    where = (
        "back in the queue" if claim["status"] == "waiting" else "left for a handler"
    )
    return f"{claim_id}: failed ({problem}), {where}"
