"""The UnderCover Agent, which decides claims through the backend's API."""

import json
import os
from typing import Any, Literal

import httpx
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

load_dotenv(override=True)

BACKEND_URL = "http://localhost:8000"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-6-luna"
CUSTOMER_FIELDS_FOR_THE_MODEL = ("name", "customer_since", "previous_claims")


def backend() -> httpx.Client:
    """Return a client for the UnderCover backend."""
    return httpx.Client(base_url=BACKEND_URL, timeout=30)


def call(method: str, url: str, body: dict[str, Any] | None = None) -> httpx.Response:
    """Call the backend and return its response, refusals included."""
    with backend() as client:
        return client.request(method, url, json=body)


@tool
def get_claim(claim_id: str) -> str:
    """Read a claim: the customer's story, the items claimed and the documents."""
    return call("GET", f"/api/claims/{claim_id}").text


@tool
def get_policy(policy_id: str) -> str:
    """Read the policy with the policy_id on a claim: plan, limits, add-ons and trip."""
    return call("GET", f"/api/policies/{policy_id}").text


@tool
def get_customer(customer_id: str) -> str:
    """Read the earlier claims of the customer with the customer_id on a claim."""
    response = call("GET", f"/api/customers/{customer_id}")
    if response.is_error:
        return response.text
    customer = response.json()
    return json.dumps({key: customer[key] for key in CUSTOMER_FIELDS_FOR_THE_MODEL})


@tool
def get_policy_wording() -> str:
    """Read the policy wording, which every decision follows."""
    return call("GET", "/api/policy-wording").text


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
    return call("POST", f"/api/claims/{claim_id}/decision", body).text


@tool
def pay_claim(claim_id: str, amount: float) -> str:
    """Pay an approved claim its payout, in US dollars."""
    return call("POST", f"/api/claims/{claim_id}/payment", {"amount": amount}).text


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


def steps(message: AIMessage | ToolMessage) -> list[dict[str, str]]:
    """Describe one of the agent's messages as steps for the dashboard."""
    if isinstance(message, ToolMessage):
        return [
            {"kind": "tool_result", "name": message.name or "", "content": message.text}
        ]
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
    """Work one claim, posting each step to the backend, and return the final reply."""
    with backend() as client:
        instructions = client.get("/api/instructions").raise_for_status().json()
        client.post(f"/api/claims/{claim_id}/start").raise_for_status()
        agent = create_agent(
            llm or model(), tools=TOOLS, system_prompt=instructions["text"]
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
            for message in state["messages"]
        ):
            for step in steps(message):
                client.post(
                    f"/api/claims/{claim_id}/steps",
                    json={"thread_id": thread_id, **step},
                ).raise_for_status()
            reply = message.text
    return reply
