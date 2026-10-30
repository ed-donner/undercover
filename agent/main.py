"""The UnderCover Agent."""

import os
from typing import Literal

import httpx
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool, tool
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

load_dotenv(override=True)

BACKEND_URL = "http://localhost:8000"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "deepseek/deepseek-v4.1-flash"

Document = Literal["policy_wording", "claims_manual"]


def backend() -> httpx.Client:
    """Return a client for the UnderCover backend."""
    return httpx.Client(base_url=BACKEND_URL, timeout=10)


def claim_instructions() -> str:
    """Fetch the instructions for deciding one claim from the backend."""
    with backend() as client:
        response = client.get("/api/claim-instructions")
    response.raise_for_status()
    return response.json()["instructions"]


def _record_step(claim_id: str, text: str) -> None:
    with backend() as client:
        client.post(f"/api/claims/{claim_id}/steps", json={"text": text})


def claim_tools(claim_id: str) -> list[BaseTool]:
    """Build the tools the agent uses to decide one claim."""

    @tool
    def get_claim() -> dict[str, object]:
        """Read the claim, its policy, and the customer's claim history."""
        with backend() as client:
            response = client.get(f"/api/claims/{claim_id}")
        response.raise_for_status()
        _record_step(
            claim_id, "Read the claim, its policy and the customer's claim history"
        )
        return response.json()

    @tool
    def list_sections(document: Document) -> list[str]:
        """List the section headings of the policy wording or the claims manual."""
        with backend() as client:
            response = client.get(f"/api/documents/{document}/sections")
        response.raise_for_status()
        return response.json()

    @tool
    def read_section(document: Document, heading: str) -> str:
        """Read one section of the policy wording or the claims manual."""
        with backend() as client:
            response = client.get(
                f"/api/documents/{document}/section", params={"heading": heading}
            )
        response.raise_for_status()
        title = "policy wording" if document == "policy_wording" else "claims manual"
        _record_step(claim_id, f"Read {title} section: {heading}")
        return response.json()["text"]

    @tool
    def decide_claim(
        decision: Literal["approve", "decline", "refer"],
        payout: float,
        reason: str,
        policy_reference: str,
    ) -> str:
        """Decide the claim: approve, decline, or refer, with its payout and reason."""
        with backend() as client:
            response = client.post(
                f"/api/claims/{claim_id}/decision",
                json={
                    "decision": decision,
                    "payout": payout,
                    "reason": reason,
                    "policy_reference": policy_reference,
                },
            )
        response.raise_for_status()
        detail = f" for ${payout:,.2f}" if decision == "approve" else ""
        _record_step(claim_id, f"Decided: {decision}{detail}")
        return "Recorded"

    return [get_claim, list_sections, read_section, decide_claim]


def model() -> ChatOpenAI:
    """Return the model named in MODEL_NAME, or DeepSeek V4.1 Flash by default."""
    name = os.getenv("MODEL_NAME")
    return ChatOpenAI(
        model=name or DEFAULT_MODEL,
        base_url=OPENROUTER_BASE_URL,
        api_key=SecretStr(os.environ["OPENROUTER_API_KEY"]),
        reasoning_effort=None if name else "low",
    )


def run(claim_id: str, thread_id: str, llm: BaseChatModel | None = None) -> str:
    """Run the agent on one claim and return its final reply."""
    agent = create_agent(
        llm or model(),
        tools=claim_tools(claim_id),
        system_prompt=claim_instructions(),
    )
    result = agent.invoke(
        {"messages": [{"role": "user", "content": f"Decide claim {claim_id}."}]},
        config={"configurable": {"thread_id": thread_id}},
    )
    return result["messages"][-1].text
