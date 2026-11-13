"""The API-only UnderCover claim agent."""

import json
import os
from http import HTTPStatus
from typing import Literal
from urllib.parse import quote

import httpx
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool, tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, SecretStr

load_dotenv()

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-6-luna"


class DecisionDraft(BaseModel):
    outcome: Literal["approve", "decline", "refer"]
    payout: str
    calculation: str
    explanation: str
    policy_sections: list[int]
    manual_sections: list[int]
    manual_version: str


def backend() -> httpx.Client:
    """Return a client for the UnderCover backend."""
    return httpx.Client(
        base_url=os.getenv("BACKEND_URL", "http://127.0.0.1:8000"), timeout=30
    )


def model() -> ChatOpenAI:
    """Return the configured OpenRouter model without contacting the provider."""
    name = os.getenv("MODEL_NAME")
    return ChatOpenAI(
        model=name or DEFAULT_MODEL,
        base_url=OPENROUTER_BASE_URL,
        api_key=SecretStr(os.environ["OPENROUTER_API_KEY"]),
        reasoning_effort=None if name else "low",
        timeout=60,
        max_retries=1,
    )


class ClaimTools:
    def __init__(self, client: httpx.Client, claim_id: str, run_id: str):
        self.client = client
        self.path = f"/api/claims/{quote(claim_id, safe='')}"
        self.run_id = run_id
        self.context_read = False
        self.documents_read: set[str] = set()

    def get(self, path: str):
        response = self.client.get(path)
        response.raise_for_status()
        return response.json()

    def context(self) -> dict:
        claim = self.get(self.path)
        policy = self.get(f"/api/policies/{quote(claim['policy_id'], safe='')}")
        context = {
            "claim": claim,
            "policy": policy,
            "plan": self.get(f"/api/plans/{quote(policy['plan'], safe='')}"),
            "customer": self.get(
                f"/api/customers/{quote(claim['customer_id'], safe='')}"
            ),
            "company": self.get("/api/company"),
        }
        self.context_read = True
        return context

    def event(self, activity: str) -> None:
        response = self.client.post(
            f"/api/runs/{self.run_id}/events", json={"activity": activity}
        )
        response.raise_for_status()

    def tools(self) -> list[BaseTool]:
        @tool
        def read_context() -> str:
            """Read the claim, policy, plan, customer history and company settings."""
            self.event("context_started")
            result = json.dumps(self.context())
            self.event("context_read")
            return result

        @tool
        def list_sections() -> str:
            """List section titles and versions for the wording and claims manual."""
            return json.dumps(self.get("/api/documents"))

        @tool
        def search_sections(document_id: str, query: str) -> str:
            """Search wording or manual sections and return short excerpts."""
            response = self.client.post(
                "/api/documents/search",
                json={"document_id": document_id, "query": query},
            )
            response.raise_for_status()
            return response.text

        @tool
        def read_section(document_id: str, section: int) -> str:
            """Read and audit a complete numbered wording or manual section."""
            response = self.client.post(
                f"{self.path}/reads",
                json={
                    "run_id": self.run_id,
                    "document_id": document_id,
                    "section": section,
                },
            )
            response.raise_for_status()
            self.documents_read.add(document_id)
            return response.text

        @tool
        def record_decision(decision: DecisionDraft) -> str:
            """Record a decision with a USD payout and policy section numbers."""
            if not self.context_read or self.documents_read != {"wording", "manual"}:
                raise RuntimeError("Read context, wording and manual before deciding")
            self.event("decision_started")
            response = self.client.post(
                f"{self.path}/decision",
                json={"run_id": self.run_id, **decision.model_dump()},
            )
            response.raise_for_status()
            return response.text

        @tool
        def request_payment(amount: str) -> str:
            """Request a separate simulated USD payment; sign-off may block it."""
            self.event("payment_started")
            response = self.client.post(f"{self.path}/payment", json={"amount": amount})
            if response.status_code == HTTPStatus.CONFLICT:
                return json.dumps({"paid": False, "reason": response.json()["detail"]})
            response.raise_for_status()
            return response.text

        return [
            read_context,
            list_sections,
            search_sections,
            read_section,
            record_decision,
            request_payment,
        ]


def run(claim_id: str, thread_id: str, llm: BaseChatModel | None = None) -> str:
    """Decide one claim through the backend API using the supplied thread."""
    path = f"/api/claims/{quote(claim_id, safe='')}"
    with backend() as client:
        instructions = client.get("/api/instructions")
        instructions.raise_for_status()
        runs = client.get(f"{path}/runs")
        runs.raise_for_status()
        active = [
            item
            for item in runs.json()
            if item["thread_id"] == thread_id and item["status"] == "running"
        ]
        if not active:
            raise RuntimeError("No active run for the supplied claim and thread")
        tools = ClaimTools(client, claim_id, active[0]["run_id"])
        agent = create_agent(
            llm or model(),
            tools=tools.tools(),
            system_prompt=instructions.json()["text"],
        )
        result = agent.invoke(
            {"messages": [{"role": "user", "content": f"Process claim {claim_id}."}]},
            config={"configurable": {"thread_id": thread_id}, "recursion_limit": 40},
        )
        final = tools.get(path)
        if final["decision"] is None:
            raise RuntimeError("Agent finished without recording a decision")
        limit = tools.get("/api/company")["payout_approval_limit"]
        if (
            final["decision"]["outcome"] == "approve"
            and final["decision"]["payout"] <= limit
            and final["payment"] is None
        ):
            raise RuntimeError("Agent finished without paying a below-limit approval")
        return result["messages"][-1].text
