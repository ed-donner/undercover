"""The tools of the claim agent and the queue agent."""

import json
from typing import Any, Literal

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel

from agent.base import call

Document = Literal["claims_manual", "policy_wording"]


class Todo(BaseModel):
    """One item on the to-do list."""

    text: str
    status: Literal["todo", "in_progress", "done", "for_handler"]


def instructions() -> dict[str, str]:
    """Fetch the agent's instructions from the backend."""
    return json.loads(call("GET", "/api/instructions"))


def claim_tools(claim_id: str) -> list[BaseTool]:
    """Build the tools for working one claim, each bound to that claim."""

    @tool
    def get_claim() -> str:
        """Read the claim: the story, the items and every document."""
        return call("GET", f"/api/claims/{claim_id}")

    @tool
    def look_up_policy() -> str:
        """Get the claim's policy and the limits of its plan."""
        return call("POST", f"/api/claims/{claim_id}/look-up-policy")

    @tool
    def look_up_history() -> str:
        """Get the customer's earlier claims."""
        return call("POST", f"/api/claims/{claim_id}/look-up-history")

    @tool
    def list_sections(document: Document) -> str:
        """List the numbered sections of the claims manual or the policy wording."""
        return call("GET", f"/api/documents/{document}/sections")

    @tool
    def read_section(document: Document, number: int) -> str:
        """Read one numbered section of the claims manual or the policy wording."""
        body = {"document": document, "number": number}
        return call("POST", f"/api/claims/{claim_id}/read-section", body)

    @tool
    def decide(
        decision: Literal["approve", "decline", "refer"],
        payout: float,
        policy_section: str,
        reason: str,
    ) -> str:
        """Record the decision, payout (zero unless approved), section and reason."""
        body = {
            "decision": decision,
            "payout": payout,
            "policy_section": policy_section,
            "reason": reason,
        }
        return call("POST", f"/api/claims/{claim_id}/decision", body)

    @tool
    def pay(amount: float) -> str:
        """Pay an approved claim, for exactly the payout."""
        return call("POST", f"/api/claims/{claim_id}/payment", {"amount": amount})

    return [
        get_claim,
        look_up_policy,
        look_up_history,
        list_sections,
        read_section,
        decide,
        pay,
    ]


def result_line(claim: dict[str, Any]) -> str:
    """Summarize where a claim ended up, in one line."""
    claim_id, status = claim["claim_id"], claim["status"]
    if status == "waiting":
        return f"{claim_id}: failed, back in the queue (attempt {claim['attempts']})"
    if status == "for_handler":
        return f"{claim_id}: failed twice, left for a handler"
    payout = f"${claim['payout']:,.2f}"
    if status == "awaiting_signoff":
        return f"{claim_id}: approved {payout}, waiting for sign-off"
    if claim["decision"] != "approve":
        return f"{claim_id}: {claim['decision']}"
    paid = "paid" if claim["paid"] is not None else "not paid yet"
    return f"{claim_id}: approved {payout}, {paid}"


def fail(claim_id: str, error: str) -> None:
    """Report a failure on a claim, unless it was already decided."""
    call("POST", f"/api/claims/{claim_id}/failure", {"error": error})


def work_claim(run_id: int, claim_id: str, llm: BaseChatModel, thread_id: str) -> str:
    """Work one claim with a fresh agent and return a one-line result."""
    started = json.loads(call("POST", f"/api/runs/{run_id}/claims/{claim_id}"))
    if "detail" in started:
        return f"{claim_id}: not started ({started['detail']})"
    try:
        agent = create_agent(
            llm, tools=claim_tools(claim_id), system_prompt=instructions()["claim"]
        )
        agent.invoke(
            {"messages": [{"role": "user", "content": f"Claim {claim_id}"}]},
            config={
                "configurable": {"thread_id": f"{thread_id}-{claim_id}"},
                "recursion_limit": 60,
            },
        )
    except Exception as error:  # noqa: BLE001
        fail(claim_id, f"{type(error).__name__}: {error}")
    claim = json.loads(call("GET", f"/api/claims/{claim_id}"))
    if claim["status"] == "in_progress":
        fail(claim_id, "The agent ended without a decision")
        claim = json.loads(call("GET", f"/api/claims/{claim_id}"))
    return result_line(claim)


def queue_tools(run_id: int, llm: BaseChatModel, thread_id: str) -> list[BaseTool]:
    """Build the tools for running the queue, bound to one run."""

    @tool
    def list_waiting_claims() -> str:
        """List the waiting claims this run may work, within its cap."""
        return call("GET", f"/api/runs/{run_id}/waiting")

    @tool
    def write_todos(todos: list[Todo]) -> str:
        """Replace the whole to-do list for this run, in the order you will work."""
        items = [todo.model_dump() for todo in todos]
        return call("PUT", f"/api/runs/{run_id}/todos", {"items": items})

    @tool("work_claim")
    def work_claim_tool(claim_id: str) -> str:
        """Hand one claim to a fresh helper and get back its result in one line."""
        return work_claim(run_id, claim_id, llm, thread_id)

    return [list_waiting_claims, write_todos, work_claim_tool]
