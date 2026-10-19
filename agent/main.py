"""The UnderCover Agent."""

import os
import sys
import uuid
from typing import Any, Literal

import httpx
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

load_dotenv(override=True)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-6-luna"
RESULT_LIMIT = 400


def backend() -> httpx.Client:
    """Return a client for the UnderCover backend."""
    return httpx.Client(
        base_url=os.getenv("BACKEND_URL", "http://localhost:8000"), timeout=30
    )


def request(method: str, path: str, body: dict[str, Any] | None = None):
    with backend() as client:
        return client.request(method, path, json=body)


def reply(method: str, path: str, body: dict[str, Any] | None = None) -> str:
    """Return the backend's reply, or its error, for the model to read."""
    response = request(method, path, body)
    if response.is_success:
        return response.text
    return f"Error {response.status_code}: {response.json()['detail']}"


@tool
def get_claim(claim_id: str) -> str:
    """Get a claim: the story, items, documents and where it stands."""
    return reply("GET", f"/api/claims/{claim_id}")


@tool
def get_policy(policy_id: str) -> str:
    """Get a policy: the plan, add-ons, trip dates and travelers."""
    return reply("GET", f"/api/policies/{policy_id}")


@tool
def get_customer(customer_id: str) -> str:
    """Get a customer's name and claim history."""
    return reply("GET", f"/api/customers/{customer_id}")


@tool
def get_policy_wording() -> str:
    """Get the policy wording, which every decision follows."""
    return reply("GET", "/api/policy-wording")


@tool
def record_decision(
    claim_id: str,
    decision: Literal["approve", "decline", "refer"],
    payout: float,
    explanation: str,
    policy_section: str,
) -> str:
    """Record the decision on a claim.

    The payout is 0 unless approving. The explanation is two or three sentences,
    and the policy section names the part of the wording that settles it.
    """
    body = {
        "decision": decision,
        "payout": payout,
        "explanation": explanation,
        "policy_section": policy_section,
    }
    return reply("POST", f"/api/claims/{claim_id}/decision", body)


@tool
def pay_claim(claim_id: str, amount: float) -> str:
    """Pay an approved claim of $1,000 or less the amount of its payout."""
    return reply("POST", f"/api/claims/{claim_id}/payment", {"amount": amount})


TOOLS = [
    get_claim,
    get_policy,
    get_customer,
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


def add_step(claim_id: str, kind: str, text: str) -> None:
    request("POST", f"/api/claims/{claim_id}/steps", {"kind": kind, "text": text})


def record_steps(claim_id: str, message: AnyMessage) -> None:
    """Add what a message shows the agent doing to the claim's steps."""
    if isinstance(message, ToolMessage):
        add_step(
            claim_id, "tool_result", f"{message.name}: {message.text[:RESULT_LIMIT]}"
        )
    elif isinstance(message, AIMessage):
        for call in message.tool_calls:
            add_step(claim_id, "tool_call", f"{call['name']}({call['args']})")
        if message.text:
            add_step(claim_id, "message", message.text)


def run(claim_id: str, thread_id: str, llm: BaseChatModel | None = None) -> str:
    """Run the agent on one claim and return its final reply."""
    request("POST", f"/api/claims/{claim_id}/start").raise_for_status()
    instructions = request("GET", "/api/instructions").json()["claim"]
    agent = create_agent(llm or model(), tools=TOOLS, system_prompt=instructions)
    final = ""
    try:
        for update in agent.stream(
            {"messages": [{"role": "user", "content": f"Claim {claim_id}"}]},
            config={"configurable": {"thread_id": thread_id}},
            stream_mode="updates",
        ):
            for output in update.values():
                for message in output["messages"]:
                    record_steps(claim_id, message)
                    if isinstance(message, AIMessage) and not message.tool_calls:
                        final = message.text
    except Exception as error:
        add_step(claim_id, "error", f"{type(error).__name__}: {error}")
        raise
    return final


if __name__ == "__main__":
    print(run(sys.argv[1], uuid.uuid4().hex))
