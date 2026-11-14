"""The UnderCover Agent."""

import json
import os
from collections.abc import Iterator
from typing import Any, Literal

import httpx
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

load_dotenv(override=True)

BACKEND_URL = "http://localhost:8000"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-6-luna"
STEP_LENGTH = 400


def backend() -> httpx.Client:
    """Return a client for the UnderCover backend."""
    return httpx.Client(base_url=BACKEND_URL, timeout=30)


def call(method: str, path: str, body: dict[str, Any] | None = None) -> str:
    """Call the backend, returning its refusal as text rather than raising."""
    with backend() as client:
        response = client.request(method, path, json=body)
    if response.is_client_error:
        return f"Refused: {response.json()['detail']}"
    response.raise_for_status()
    return response.text


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
def get_policy_wording() -> str:
    """Get the policy wording that decisions follow."""
    return call("GET", "/api/policy-wording")


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
    get_policy_wording,
    record_decision,
    pay_claim,
]


def model() -> ChatOpenAI:
    """Return the model named in MODEL_NAME, or GPT-6 Luna by default."""
    name = os.getenv("MODEL_NAME")
    return ChatOpenAI(
        model=name or DEFAULT_MODEL,
        base_url=OPENROUTER_BASE_URL,
        api_key=SecretStr(os.environ["OPENROUTER_API_KEY"]),
        reasoning_effort=None if name else "low",
    )


def shorten(text: str) -> str:
    """Shorten long text for a step."""
    return text if len(text) <= STEP_LENGTH else text[:STEP_LENGTH] + "..."


def steps(message: BaseMessage) -> Iterator[tuple[str, str]]:
    """Describe a message from the agent as steps for the dashboard."""
    if isinstance(message, ToolMessage):
        yield "tool_result", f"{message.name}: {shorten(message.text)}"
    elif isinstance(message, AIMessage):
        if message.text:
            yield "message", message.text
        for call_ in message.tool_calls:
            yield "tool_call", f"{call_['name']}({json.dumps(call_['args'])})"


def run(claim_id: str, thread_id: str, llm: BaseChatModel | None = None) -> str:
    """Run the agent on one claim, reporting each step, and return its final reply."""
    started = call("POST", f"/api/claims/{claim_id}/start")
    if started.startswith("Refused"):
        return started
    instructions = json.loads(call("GET", "/api/instructions"))["instructions"]
    agent = create_agent(llm or model(), tools=TOOLS, system_prompt=instructions)
    reply = ""
    for update in agent.stream(
        {"messages": [{"role": "user", "content": f"Please decide claim {claim_id}."}]},
        config={"configurable": {"thread_id": thread_id}},
        stream_mode="updates",
    ):
        for node in update.values():
            for message in node["messages"]:
                for kind, content in steps(message):
                    call(
                        "POST",
                        f"/api/claims/{claim_id}/steps",
                        {"kind": kind, "content": content},
                    )
                reply = message.text
    return reply
