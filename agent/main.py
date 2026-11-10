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
from pydantic import SecretStr

load_dotenv()

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-6-luna"


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
    )


class ClaimTools:
    def __init__(self, client: httpx.Client, claim_id: str, run_id: str):
        self.client = client
        self.path = f"/api/claims/{quote(claim_id, safe='')}"
        self.run_id = run_id
        self.context_read = False
        self.wording_read = False

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

    def tools(self) -> list[BaseTool]:
        @tool
        def read_context() -> str:
            """Read the claim, policy, plan, customer history and company settings."""
            return json.dumps(self.context())

        @tool
        def read_wording() -> str:
            """Read the full policy wording used to decide coverage and payout."""
            wording = self.get("/api/wording")
            self.wording_read = True
            return json.dumps(wording)

        @tool
        def record_decision(
            outcome: Literal["approve", "decline", "refer"],
            payout: str,
            calculation: str,
            explanation: str,
            policy_sections: list[int],
        ) -> str:
            """Record a decision with a USD payout and policy section numbers."""
            if not self.context_read or not self.wording_read:
                raise RuntimeError("Read context and wording before deciding")
            response = self.client.post(
                f"{self.path}/decision",
                json={
                    "run_id": self.run_id,
                    "outcome": outcome,
                    "payout": payout,
                    "calculation": calculation,
                    "explanation": explanation,
                    "policy_sections": policy_sections,
                },
            )
            response.raise_for_status()
            return response.text

        @tool
        def request_payment(amount: str) -> str:
            """Request a separate simulated USD payment; sign-off may block it."""
            response = self.client.post(f"{self.path}/payment", json={"amount": amount})
            if response.status_code == HTTPStatus.CONFLICT:
                return json.dumps({"paid": False, "reason": response.json()["detail"]})
            response.raise_for_status()
            return response.text

        return [read_context, read_wording, record_decision, request_payment]


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
        return result["messages"][-1].text
