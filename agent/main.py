"""The UnderCover Agent."""

import os

import httpx
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

load_dotenv(override=True)

BACKEND_URL = "http://localhost:8000"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-6-luna"


def backend() -> httpx.Client:
    """Return a client for the UnderCover backend."""
    return httpx.Client(base_url=BACKEND_URL, timeout=30)


@tool
def get_claim(claim_id: str) -> dict:
    """Return a claim with its customer, policy and plan."""
    with backend() as client:
        response = client.get(f"/api/claims/{claim_id}")
    response.raise_for_status()
    return response.json()


@tool
def get_policy_wording() -> str:
    """Return the policy wording."""
    with backend() as client:
        response = client.get("/api/policy-wording")
    response.raise_for_status()
    return response.json()["content"]


@tool
def decide_claim(
    claim_id: str, decision: str, payout: float, reason: str, reference: str
) -> dict:
    """Record a decision on a claim: approve, decline or refer."""
    with backend() as client:
        response = client.post(
            f"/api/claims/{claim_id}/decide",
            json={
                "decision": decision,
                "payout": payout,
                "reason": reason,
                "reference": reference,
            },
        )
    response.raise_for_status()
    return response.json()


@tool
def pay_claim(claim_id: str, amount: float) -> dict:
    """Pay an approved claim, or hold it for sign-off if it's over the limit."""
    with backend() as client:
        response = client.post(f"/api/claims/{claim_id}/pay", json={"amount": amount})
    response.raise_for_status()
    return response.json()


TOOLS = [get_claim, get_policy_wording, decide_claim, pay_claim]


def instructions() -> str:
    """Return the agent's instructions, fetched from the backend."""
    with backend() as client:
        response = client.get("/api/agent-instructions")
    response.raise_for_status()
    return response.json()["content"]


def model() -> ChatOpenAI:
    """Return the model named in MODEL_NAME, or GPT-6 Luna by default."""
    name = os.getenv("MODEL_NAME")
    return ChatOpenAI(
        model=name or DEFAULT_MODEL,
        base_url=OPENROUTER_BASE_URL,
        api_key=SecretStr(os.environ["OPENROUTER_API_KEY"]),
        reasoning_effort=None if name else "low",
    )


def run(claim_id: str, thread_id: str, llm: BaseChatModel | None = None) -> str:
    """Run the agent on one claim and return its final reply."""
    agent = create_agent(llm or model(), tools=TOOLS, system_prompt=instructions())
    result = agent.invoke(
        {"messages": [{"role": "user", "content": f"Decide claim {claim_id}."}]},
        config={"configurable": {"thread_id": thread_id}},
    )
    return result["messages"][-1].text
