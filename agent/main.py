"""The UnderCover Agent."""

import os
import uuid
from typing import Any, Literal

import httpx
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

load_dotenv(override=True)

BACKEND_URL = "http://localhost:8000"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-6-luna"
STEP_LENGTH = 300
# Backoff long enough to wait out a per-minute rate limit.
MODEL_RETRIES = 10


def backend() -> httpx.Client:
    """Return a client for the UnderCover backend."""
    return httpx.Client(base_url=BACKEND_URL, timeout=30)


def call(method: str, path: str, body: dict[str, Any] | None = None) -> str:
    """Call the backend and return its reply, or the reason it refused."""
    with backend() as client:
        response = client.request(method, path, json=body)
    if response.is_error:
        return f"Refused ({response.status_code}): {response.text}"
    return response.text


@tool
def start_claim(claim_id: str) -> str:
    """Take a waiting claim from the queue and mark it in progress."""
    return call("POST", f"/api/claims/{claim_id}/start")


@tool
def get_claim(claim_id: str) -> str:
    """Get a claim in full: the story, the items claimed and the documents."""
    return call("GET", f"/api/claims/{claim_id}")


@tool
def get_policy(claim_id: str) -> str:
    """Get the policy for a claim, with its plan limits, add-ons, trip and travelers."""
    return call("GET", f"/api/claims/{claim_id}/policy")


@tool
def get_claim_history(claim_id: str) -> str:
    """Get the customer's earlier claims."""
    return call("GET", f"/api/claims/{claim_id}/history")


@tool
def get_policy_wording() -> str:
    """Get the policy wording, the contract that decisions follow."""
    return call("GET", "/api/policy-wording")


@tool
def record_decision(
    claim_id: str,
    decision: Literal["approve", "decline", "refer"],
    payout: float,
    reason: str,
    policy_section: str,
) -> str:
    """Record the decision on a claim: the payout (0 unless approved), two or three
    sentences of reasons, and the policy section it rests on."""
    return call(
        "POST",
        f"/api/claims/{claim_id}/decision",
        {
            "decision": decision,
            "payout": payout,
            "reason": reason,
            "policy_section": policy_section,
        },
    )


@tool
def pay_claim(claim_id: str, amount: float) -> str:
    """Pay the approved payout on a claim. Payouts over $1,000 wait for sign-off."""
    return call("POST", f"/api/claims/{claim_id}/payment", {"amount": amount})


TOOLS = [
    start_claim,
    get_claim,
    get_policy,
    get_claim_history,
    get_policy_wording,
    record_decision,
    pay_claim,
]


ACTIONS = {
    "start_claim": "Taking the claim from the queue",
    "get_claim": "Reading the claim",
    "get_policy": "Reading the policy and its plan",
    "get_claim_history": "Reading the customer's earlier claims",
    "get_policy_wording": "Reading the policy wording",
}


def describe(name: str, inputs: dict[str, Any]) -> str:
    """Describe a tool call in plain words for the dashboard."""
    if name == "record_decision":
        return (
            f"Recording the decision: {inputs['decision']}, payout"
            f" ${inputs['payout']:,.2f}, {inputs['policy_section']}. {inputs['reason']}"
        )
    if name == "pay_claim":
        return f"Paying ${inputs['amount']:,.2f}"
    return ACTIONS[name]


class StepRecorder(BaseCallbackHandler):
    """Posts what the agent does on a claim to the backend, step by step."""

    def __init__(self, claim_id: str) -> None:
        self.claim_id = claim_id

    def record(self, text: str) -> None:
        """Post one step, shortened to fit the dashboard."""
        if len(text) > STEP_LENGTH:
            text = text[:STEP_LENGTH] + "..."
        call("POST", f"/api/claims/{self.claim_id}/steps", {"text": text})

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        inputs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        self.record(describe(serialized["name"], inputs or {}))

    def on_tool_end(self, output: ToolMessage, **kwargs: Any) -> None:
        if str(output.content).startswith("Refused"):
            self.record(f"{output.name} was refused: {output.content}")


def model() -> ChatOpenAI:
    """Return the model named in MODEL_NAME, or GPT-6 Luna by default."""
    name = os.getenv("MODEL_NAME")
    return ChatOpenAI(
        model=name or DEFAULT_MODEL,
        base_url=OPENROUTER_BASE_URL,
        api_key=SecretStr(os.environ["OPENROUTER_API_KEY"]),
        reasoning_effort=None if name else "low",
        max_retries=MODEL_RETRIES,
    )


def instructions() -> str:
    """Fetch the agent's instructions from the backend."""
    with backend() as client:
        return client.get("/api/instructions").raise_for_status().json()["text"]


def run(claim_id: str, thread_id: str, llm: BaseChatModel | None = None) -> str:
    """Run the agent on one claim and return its final reply."""
    agent = create_agent(llm or model(), tools=TOOLS, system_prompt=instructions())
    recorder = StepRecorder(claim_id)
    result = agent.invoke(
        {"messages": [{"role": "user", "content": f"Work claim {claim_id}."}]},
        config={"configurable": {"thread_id": thread_id}, "callbacks": [recorder]},
    )
    reply = result["messages"][-1].text
    recorder.record(f"Finished: {reply}")
    return reply


def waiting_claims() -> list[str]:
    """List the ids of the waiting claims, in queue order."""
    with backend() as client:
        claims = client.get("/api/claims").raise_for_status().json()
    return [c["claim_id"] for c in claims if c["status"] == "waiting"]


def main(args: list[str], llm: BaseChatModel | None = None) -> None:
    """Work the claims named in args, or every waiting claim in queue order."""
    for claim_id in args or waiting_claims():
        print(f"{claim_id}: {run(claim_id, f'{claim_id}-{uuid.uuid4().hex[:8]}', llm)}")
