"""The agent's only HTTP boundary to the UnderCover backend."""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from http import HTTPStatus
from urllib.parse import quote

import httpx
from dotenv import load_dotenv


def identifier(value: str) -> str:
    return quote(value, safe="")


class BackendAPI:
    def __init__(self, client: httpx.Client):
        self.client = client

    def _request(self, method: str, path: str, body: dict | None = None):
        response = self.client.request(method, path, json=body)
        response.raise_for_status()
        return response.json()

    def instructions(self, role: str) -> str:
        return self._request("GET", f"/api/instructions/{identifier(role)}")["text"]

    def claims(self) -> list[dict]:
        return self._request("GET", "/api/claims")

    def claim(self, claim_id: str) -> dict:
        return self._request("GET", f"/api/claims/{identifier(claim_id)}")

    def policy(self, policy_id: str) -> dict:
        return self._request("GET", f"/api/policies/{identifier(policy_id)}")

    def plan(self, name: str) -> dict:
        return self._request("GET", f"/api/plans/{identifier(name)}")

    def customer(self, customer_id: str) -> dict:
        return self._request("GET", f"/api/customers/{identifier(customer_id)}")

    def company(self) -> dict:
        return self._request("GET", "/api/company")

    def sections(self) -> list[dict]:
        return self._request("GET", "/api/documents")

    def search_sections(self, document_id: str, query: str) -> list[dict]:
        return self._request(
            "POST",
            "/api/documents/search",
            {"document_id": document_id, "query": query},
        )

    def read_section(
        self, claim_id: str, run_id: str, document_id: str, section: int
    ) -> dict:
        return self._request(
            "POST",
            f"/api/claims/{identifier(claim_id)}/reads",
            {"run_id": run_id, "document_id": document_id, "section": section},
        )

    def record_decision(self, claim_id: str, run_id: str, decision: dict) -> dict:
        return self._request(
            "POST",
            f"/api/claims/{identifier(claim_id)}/decision",
            {**decision, "run_id": run_id},
        )

    def pay(self, claim_id: str, run_id: str, amount: str) -> dict:
        try:
            return self._request(
                "POST",
                f"/api/claims/{identifier(claim_id)}/agent-payment",
                {"run_id": run_id, "amount": amount},
            )
        except httpx.HTTPStatusError as error:
            if error.response.status_code != HTTPStatus.CONFLICT:
                raise
            return {"paid": False, "reason": error.response.json()["detail"]}

    def attempts(self, claim_id: str) -> list[dict]:
        return self._request("GET", f"/api/claims/{identifier(claim_id)}/runs")

    def start_attempt(self, claim_id: str, parent_run_id: str) -> dict:
        return self._request(
            "POST",
            f"/api/claims/{identifier(claim_id)}/runs",
            {"parent_run_id": parent_run_id},
        )

    def finish_attempt(self, run_id: str) -> None:
        self._request(
            "POST",
            f"/api/runs/{identifier(run_id)}/finish",
            {"error": "Agent could not finish."},
        )

    def event(self, run_id: str, activity: str) -> None:
        self._request(
            "POST", f"/api/runs/{identifier(run_id)}/events", {"activity": activity}
        )

    def start_run(self, request: dict) -> dict:
        return self._request("POST", "/api/agent-runs", request)

    def run(self, run_id: str) -> dict:
        return self._request("GET", f"/api/agent-runs/{identifier(run_id)}")

    def write_todos(self, run_id: str, tasks: list[dict]) -> dict:
        return self._request(
            "PUT", f"/api/agent-runs/{identifier(run_id)}/tasks", {"tasks": tasks}
        )

    def check_run(self, run_id: str) -> dict:
        return self._request("POST", f"/api/agent-runs/{identifier(run_id)}/check")

    def finish_run(self, run_id: str) -> dict:
        return self._request(
            "POST", f"/api/agent-runs/{identifier(run_id)}/finish", {"error": None}
        )


@contextmanager
def connect() -> Iterator[BackendAPI]:
    load_dotenv()
    with httpx.Client(
        base_url=os.getenv("BACKEND_URL", "http://127.0.0.1:8000"), timeout=30
    ) as client:
        yield BackendAPI(client)
