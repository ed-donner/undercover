"""The claim agent, which decides one claim through the backend's API."""

import json
import uuid
from typing import Any, Literal

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool

from agent import common
from agent.common import money

CUSTOMER_FIELDS_FOR_THE_MODEL = ("name", "customer_since", "previous_claims")
MODEL_CALLS = 25
LONGEST_ERROR = 200


@tool
def get_claim(claim_id: str) -> str:
    """Read a claim: the customer's story, the items claimed and the documents."""
    return common.call("GET", f"/api/claims/{claim_id}").text


@tool
def get_policy(policy_id: str) -> str:
    """Read the policy with the policy_id on a claim: plan, limits, add-ons and trip."""
    return common.call("GET", f"/api/policies/{policy_id}").text


@tool
def get_customer(customer_id: str) -> str:
    """Read the earlier claims of the customer with the customer_id on a claim."""
    response = common.call("GET", f"/api/customers/{customer_id}")
    if response.is_error:
        return response.text
    customer = response.json()
    return json.dumps({key: customer[key] for key in CUSTOMER_FIELDS_FOR_THE_MODEL})


@tool
def list_sections() -> str:
    """List the sections of the policy wording and the claims manual."""
    return common.call("GET", "/api/documents/sections").text


@tool
def search_documents(query: str) -> str:
    """Search the policy wording and the claims manual for the sections on a topic."""
    return common.call("GET", "/api/documents/search", params={"query": query}).text


@tool
def read_section(
    document: Literal["policy_wording", "claims_manual"], section: int
) -> str:
    """Read one numbered section of the policy wording or the claims manual."""
    return common.call("GET", f"/api/documents/{document}/sections/{section}").text


@tool
def record_decision(
    claim_id: str,
    decision: Literal["approve", "decline", "refer"],
    payout: float,
    reason: str,
    policy_section: str,
) -> str:
    """Record your final decision on a claim, with the payout in US dollars."""
    body = {
        "decision": decision,
        "payout": payout,
        "reason": reason,
        "policy_section": policy_section,
    }
    return common.call("POST", f"/api/claims/{claim_id}/decision", body).text


@tool
def pay_claim(claim_id: str, amount: float) -> str:
    """Pay an approved claim its payout, in US dollars."""
    return common.call(
        "POST", f"/api/claims/{claim_id}/payment", {"amount": amount}
    ).text


TOOLS = [
    get_claim,
    get_policy,
    get_customer,
    list_sections,
    search_documents,
    read_section,
    record_decision,
    pay_claim,
]


def claim(claim_id: str) -> dict[str, Any]:
    """Read a claim back from the backend."""
    return common.call("GET", f"/api/claims/{claim_id}").raise_for_status().json()


def unfinished(claim_id: str) -> str | None:
    """Say what's left to do on a claim, if anything."""
    current = claim(claim_id)
    if current["decision"] is None:
        return (
            f"You haven't recorded a decision on {claim_id}."
            " Decide it and record the decision before you finish."
        )
    if current["status"] == "in_progress":
        return (
            f"You approved {claim_id} for {money(current['payout'])} but haven't"
            " paid it. Pay it before you finish."
        )
    return None


def steps(message: AnyMessage) -> list[dict[str, str]]:
    """Describe one of the agent's messages as steps for the dashboard."""
    if isinstance(message, ToolMessage):
        return [
            {"kind": "tool_result", "name": message.name or "", "content": message.text}
        ]
    if isinstance(message, HumanMessage):
        return [{"kind": "reminder", "name": "harness", "content": message.text}]
    if not isinstance(message, AIMessage):
        return []
    reply = [{"kind": "reply", "name": "agent", "content": message.text}]
    return (reply if message.text else []) + [
        {
            "kind": "tool_call",
            "name": tool_call["name"],
            "content": json.dumps(tool_call["args"]),
        }
        for tool_call in message.tool_calls
    ]


def run(claim_id: str, thread_id: str, llm: BaseChatModel | None = None) -> str:
    """Run one attempt at a started claim, posting each step, and return the reply."""
    instructions = common.call("GET", "/api/instructions").raise_for_status().json()
    agent = create_agent(
        llm or common.model(),
        tools=TOOLS,
        system_prompt=instructions["text"],
        middleware=common.harness(MODEL_CALLS, lambda: unfinished(claim_id)),
    )
    updates = agent.stream(
        {"messages": [{"role": "user", "content": f"Decide claim {claim_id}."}]},
        config={"configurable": {"thread_id": thread_id}},
        stream_mode="updates",
    )
    reply = ""
    for message in (
        message
        for update in updates
        for state in update.values()
        for message in (state or {}).get("messages", [])
    ):
        for step in steps(message):
            post_step(claim_id, thread_id, step)
        reply = message.text
    return reply


def post_step(claim_id: str, thread_id: str, step: dict[str, str]) -> None:
    """Record one step on a claim."""
    common.call(
        "POST", f"/api/claims/{claim_id}/steps", {"thread_id": thread_id, **step}
    ).raise_for_status()


def outcome(decided: dict[str, Any]) -> str:
    """Say in one line how a finished claim ended."""
    claim_id = decided["claim_id"]
    if decided["decision"] == "decline":
        return f"{claim_id}: declined."
    if decided["decision"] == "refer":
        return f"{claim_id}: referred."
    payout = money(decided["payout"])
    if decided["status"] == "waiting_for_sign_off":
        return f"{claim_id}: approved {payout}, waiting for a handler's sign-off."
    return f"{claim_id}: approved {payout} and paid."


def what_went_wrong(current: dict[str, Any], error: Exception | None) -> str:
    """Describe a failed attempt in a few words."""
    if error is not None:
        first_line = str(error).partition("\n")[0].rstrip(".")
        return f"{type(error).__name__}: {first_line}"[:LONGEST_ERROR]
    if current["decision"] is None:
        return "the agent stopped without recording a decision"
    return f"the agent approved {money(current['payout'])} but didn't pay it"


def work(claim_id: str, llm: BaseChatModel | None = None) -> str:
    """Start a claim, make one attempt at it in a fresh context, and report a line."""
    started = common.call("POST", f"/api/claims/{claim_id}/start")
    if started.is_error:
        return common.detail(started)
    thread_id = str(uuid.uuid4())
    error = None
    try:
        run(claim_id, thread_id, llm)
    except Exception as failure:  # One bad claim must never stop the run.
        error = failure
    current = claim(claim_id)
    if current["status"] in ("decided", "waiting_for_sign_off"):
        return outcome(current)
    what = what_went_wrong(current, error)
    released = common.call("POST", f"/api/claims/{claim_id}/release")
    after = (
        "It's back in the queue for one more try."
        if released.raise_for_status().json()["status"] == "waiting"
        else "It's left for a handler."
    )
    post_step(
        claim_id,
        thread_id,
        {
            "kind": "failure",
            "name": "harness",
            "content": f"This attempt failed: {what}. {after}",
        },
    )
    return f"{claim_id} failed: {what}. {after}"
