"""One planning agent delegates sequentially through the claims API."""

import json
import time
from collections.abc import Callable
from urllib.parse import quote

import httpx
from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware, ModelRetryMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel

from agent.main import backend, model
from agent.middleware import transient

POLL_SECONDS = 0.25
DELEGATION_SECONDS = 490


class PlannedTask(BaseModel):
    claim_id: str
    state: str


class QueueGuard(AgentMiddleware):
    def __init__(self, state: Callable[[], dict]):
        self.state = state

    def before_model(self, state, runtime):
        if self.state()["status"] != "running":
            raise RuntimeError("Queue run is no longer active")

    def wrap_tool_call(self, request, handler):
        try:
            return handler(request)
        except httpx.HTTPStatusError as error:
            if error.response.status_code not in (400, 404, 409, 422):
                raise
            return ToolMessage(
                content=(
                    "Step rejected. Read persisted queue state and the "
                    "completion check, then correct the plan within its cap."
                ),
                tool_call_id=request.tool_call["id"],
                status="error",
            )


class QueueTools:
    def __init__(self, client: httpx.Client, run_id: str):
        self.client = client
        self.path = f"/api/agent-runs/{quote(run_id, safe='')}"
        self.run_id = run_id

    def state(self) -> dict:
        response = self.client.get(self.path)
        response.raise_for_status()
        return response.json()

    def delegate(self, claim_id: str) -> str:
        path = f"/api/claims/{quote(claim_id, safe='')}"
        current = self.state()
        previous = next(
            (t for t in current["tasks"] if t["claim_id"] == claim_id), None
        )
        if previous and previous["state"] in ("done", "needs_handler"):
            return f"{claim_id}: {previous['reason']}"
        response = self.client.post(f"{path}/runs", json={"parent_run_id": self.run_id})
        response.raise_for_status()
        run_id = response.json()["run_id"]
        deadline = time.monotonic() + DELEGATION_SECONDS
        while True:
            attempts = self.client.get(f"{path}/runs")
            attempts.raise_for_status()
            attempt = next(r for r in attempts.json() if r["run_id"] == run_id)
            if attempt["status"] != "running":
                break
            if time.monotonic() >= deadline:
                stopped = self.client.post(
                    f"/api/runs/{run_id}/finish",
                    json={"error": "Agent could not finish."},
                )
                stopped.raise_for_status()
                break
            time.sleep(POLL_SECONDS)
        claim = self.client.get(path)
        claim.raise_for_status()
        return claim_summary(claim.json())

    def tools(self) -> list[BaseTool]:
        @tool
        def read_queue() -> str:
            """Read scope, cap, persisted tasks and lightweight claim metadata."""
            state = self.state()
            response = self.client.get("/api/claims")
            response.raise_for_status()
            state["claims"] = [
                {
                    key: claim[key]
                    for key in (
                        "claim_id",
                        "claim_type",
                        "amount_claimed",
                        "status",
                        "needs_handler",
                        "failures",
                    )
                }
                for claim in response.json()
                if claim["claim_id"] in state["scope"]
            ]
            return json.dumps(state)

        @tool
        def write_todos(tasks: list[PlannedTask]) -> str:
            """Persist ordered tasks; use existing states and todo for new work."""
            response = self.client.put(
                f"{self.path}/tasks", json={"tasks": [t.model_dump() for t in tasks]}
            )
            response.raise_for_status()
            return response.text

        @tool
        def delegate_claim(claim_id: str) -> str:
            """Delegate a planned claim to a fresh helper and return one result line."""
            return self.delegate(claim_id)

        @tool
        def check_completion() -> str:
            """Check for missing work within the cap before trying to finish."""
            response = self.client.post(f"{self.path}/check")
            response.raise_for_status()
            return response.text

        @tool(return_direct=True)
        def finish_run() -> str:
            """Finalize a checked run and return the stored summary."""
            response = self.client.post(f"{self.path}/finish", json={"error": None})
            response.raise_for_status()
            return response.json()["summary"]

        return [read_queue, write_todos, delegate_claim, check_completion, finish_run]


def claim_summary(claim: dict) -> str:
    decision = claim["decision"]
    if decision is None:
        reason = (
            claim["handler_reason"]
            if claim["needs_handler"]
            else "failed; retry available"
        )
        return f"{claim['claim_id']}: {reason}"
    outcome = decision["outcome"]
    payment = "paid" if claim["payment"] else "unpaid"
    if claim["status"] == "waiting_for_sign_off":
        payment = "waiting for sign-off"
    return f"{claim['claim_id']}: {outcome}, ${decision['payout']:,.2f}, {payment}"


def run_queue(run_id: str, thread_id: str, llm: BaseChatModel | None = None) -> str:
    """Plan and work a bounded queue through fresh claim helpers."""
    with backend() as client:
        tools = QueueTools(client, run_id)
        state = tools.state()
        instructions = client.get("/api/instructions/queue")
        instructions.raise_for_status()
        agent = create_agent(
            llm or model(),
            tools=tools.tools(),
            system_prompt=instructions.json()["text"],
            middleware=[
                ModelRetryMiddleware(
                    max_retries=1,
                    retry_on=transient,
                    on_failure="error",
                    initial_delay=0.2,
                    jitter=False,
                ),
                QueueGuard(tools.state),
            ],
        )
        agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            f"Work run {run_id}. Read its persisted plan "
                            "and scope; work every eligible claim within "
                            "its cap, then check and finish."
                        ),
                    }
                ]
            },
            config={
                "configurable": {"thread_id": thread_id},
                "recursion_limit": max(40, state["max_claims"] * 16 + 20),
            },
        )
        final = tools.state()
        if final["status"] != "completed":
            raise RuntimeError("Agent did not complete the checked run")
        return final["summary"]
