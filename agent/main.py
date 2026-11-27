"""The UnderCover Agent, which decides one claim through the backend's API."""

import json
import os
from typing import Any, Literal

import httpx
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.tools import BaseTool, tool
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

load_dotenv(override=True)

# 127.0.0.1, not localhost: on Windows localhost tries IPv6 first and waits.
BACKEND_URL = "http://127.0.0.1:8000"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-6-luna"
STEP_LIMIT = 1000


def backend() -> httpx.Client:
    """Return a client for the UnderCover backend."""
    return httpx.Client(base_url=BACKEND_URL, timeout=30)


def request(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
    """Call the backend and return the JSON reply, raising on an error."""
    with backend() as client:
        response = client.request(method, path, json=body)
    response.raise_for_status()
    return response.json()


def tool_request(method: str, path: str, body: dict[str, Any] | None = None) -> str:
    """Call the backend for a tool, returning an error as text the model can read."""
    with backend() as client:
        response = client.request(method, path, json=body)
    if response.is_error:
        return f"Refused ({response.status_code}): {response.json()['detail']}"
    return response.text


def claim_tools(claim_id: str) -> list[BaseTool]:
    """Return the agent's tools, with the decision and payment bound to this claim."""

    @tool
    def get_claim() -> str:
        """Get the claim: the customer's story, the items claimed and the documents."""
        return tool_request("GET", f"/api/claims/{claim_id}")

    @tool
    def get_policy(policy_id: str) -> str:
        """Get a policy with its plan's limits, deductible and add-ons."""
        return tool_request("GET", f"/api/policies/{policy_id}")

    @tool
    def get_customer(customer_id: str) -> str:
        """Get a customer and their earlier claims."""
        return tool_request("GET", f"/api/customers/{customer_id}")

    @tool
    def get_policy_wording() -> str:
        """Get the policy wording, the contract that decisions follow."""
        return tool_request("GET", "/api/policy-wording")

    @tool
    def record_decision(
        decision: Literal["approve", "decline", "refer"],
        payout: float,
        calculation: str,
        reasons: str,
        policy_section: str,
    ) -> str:
        """Record the decision on the claim, with the payout in US dollars."""
        return tool_request(
            "POST",
            f"/api/claims/{claim_id}/decision",
            {
                "decision": decision,
                "payout": payout,
                "calculation": calculation,
                "reasons": reasons,
                "policy_section": policy_section,
            },
        )

    @tool
    def pay_claim(amount: float) -> str:
        """Pay the approved payout on the claim, in US dollars."""
        return tool_request(
            "POST", f"/api/claims/{claim_id}/payment", {"amount": amount}
        )

    return [
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


def steps(message: BaseMessage) -> list[dict[str, str]]:
    """Describe one message from the agent as steps for the dashboard."""
    if isinstance(message, ToolMessage):
        content = message.text
        if len(content) > STEP_LIMIT:
            content = content[:STEP_LIMIT] + "..."
        return [{"kind": "tool_result", "content": f"{message.name}: {content}"}]
    if isinstance(message, AIMessage):
        found = [
            {"kind": "tool_call", "content": f"{c['name']} {json.dumps(c['args'])}"}
            for c in message.tool_calls
        ]
        if message.text:
            found.insert(0, {"kind": "message", "content": message.text})
        return found
    return []


def record_step(claim_id: str, step: dict[str, str]) -> None:
    request("POST", f"/api/claims/{claim_id}/steps", step)


def run(claim_id: str, thread_id: str, llm: BaseChatModel | None = None) -> str:
    """Run the agent on one claim and return its final reply."""
    instructions = request("GET", "/api/instructions")["text"]
    status = request("GET", f"/api/claims/{claim_id}")["status"]
    if status == "waiting":
        request("POST", f"/api/claims/{claim_id}/start")
    elif status != "in_progress":
        raise ValueError(f"{claim_id} is {status}, so there is nothing to decide")
    reply = ""
    try:
        agent = create_agent(
            llm or model(), tools=claim_tools(claim_id), system_prompt=instructions
        )
        for update in agent.stream(
            {"messages": [{"role": "user", "content": f"Decide claim {claim_id}."}]},
            config={"configurable": {"thread_id": thread_id}},
            stream_mode="updates",
        ):
            for node in update.values():
                for message in (node or {}).get("messages", []):
                    for step in steps(message):
                        record_step(claim_id, step)
                    if isinstance(message, AIMessage) and message.text:
                        reply = message.text
    except Exception as error:
        record_step(claim_id, {"kind": "error", "content": str(error)})
        release_if_in_progress(claim_id)
        raise
    if release_if_in_progress(claim_id):
        record_step(
            claim_id,
            {"kind": "error", "content": "The agent stopped without a decision."},
        )
    return reply


def release_if_in_progress(claim_id: str) -> bool:
    """Put the claim back in the queue if no decision was recorded."""
    if request("GET", f"/api/claims/{claim_id}")["status"] != "in_progress":
        return False
    request("POST", f"/api/claims/{claim_id}/release")
    return True
