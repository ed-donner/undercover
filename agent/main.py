"""The UnderCover Agent."""

import json
import os
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

BACKEND_URL = "http://127.0.0.1:8000"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-6-luna"
RESULT_LENGTH = 300


def backend() -> httpx.Client:
    """Return a client for the UnderCover backend."""
    return httpx.Client(base_url=BACKEND_URL, timeout=30)


def call(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
    """Call the backend. A refusal comes back as the backend's message."""
    with backend() as client:
        response = client.request(method, path, json=body)
    if response.is_server_error:
        response.raise_for_status()
    return response.json()


@tool
def get_claim(claim_id: str) -> Any:
    """Get a claim: the customer's story, the items claimed and the documents."""
    return call("GET", f"/api/claims/{claim_id}")


@tool
def get_policy(policy_id: str) -> Any:
    """Get a policy with its plan's limits, its add-ons, the trip and travelers."""
    return call("GET", f"/api/policies/{policy_id}")


@tool
def get_claim_history(customer_id: str) -> Any:
    """Get the customer's earlier claims."""
    return call("GET", f"/api/customers/{customer_id}/claims")


@tool
def get_policy_wording() -> Any:
    """Get the policy wording that decisions must follow."""
    return call("GET", "/api/policy-wording")


@tool
def record_decision(
    claim_id: str,
    decision: Literal["approve", "decline", "refer"],
    payout: float,
    reason: str,
    policy_section: str,
) -> Any:
    """Record the decision on a claim with the payout, the reason and the section."""
    body = {
        "decision": decision,
        "payout": payout,
        "reason": reason,
        "policy_section": policy_section,
    }
    return call("POST", f"/api/claims/{claim_id}/decision", body)


@tool
def pay_claim(claim_id: str, amount: float) -> Any:
    """Pay an approved claim its payout."""
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


def steps(message: BaseMessage) -> list[tuple[str, str]]:
    """Describe a message from the agent as steps for the dashboard."""
    if isinstance(message, ToolMessage):
        return [("tool_result", f"{message.name}: {message.text[:RESULT_LENGTH]}")]
    if isinstance(message, AIMessage) and message.tool_calls:
        return [
            (
                "tool_call",
                f"{call['name']}({json.dumps(call['args'], ensure_ascii=False)})",
            )
            for call in message.tool_calls
        ]
    if isinstance(message, AIMessage):
        return [("reply", message.text)]
    return []


def run(claim_id: str, thread_id: str, llm: BaseChatModel | None = None) -> str:
    """Run the agent on one claim, record each step, and return its final reply."""
    instructions = call("GET", "/api/instructions")["text"]
    agent = create_agent(llm or model(), tools=TOOLS, system_prompt=instructions)
    reply = ""
    for update in agent.stream(
        {"messages": [{"role": "user", "content": f"Decide claim {claim_id}."}]},
        config={"configurable": {"thread_id": thread_id}},
        stream_mode="updates",
    ):
        for node in update.values():
            for message in (node or {}).get("messages", []):
                for kind, text in steps(message):
                    call(
                        "POST",
                        f"/api/claims/{claim_id}/steps",
                        {"kind": kind, "text": text},
                    )
                    if kind == "reply":
                        reply = text
    return reply
