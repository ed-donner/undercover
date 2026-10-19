"""The queue agent: plans a run, hands each claim to a claim agent and reports."""

import json
import uuid
from typing import Any, Literal

from langchain.agents import create_agent
from langchain.agents.middleware import AgentState, after_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import BaseTool, tool
from langgraph.runtime import Runtime
from pydantic import BaseModel

from agent import claim_agent, harness
from agent.harness import failure, request

CALL_LIMIT = 200
NUDGES = 3


class TodoItem(BaseModel):
    text: str
    status: Literal["todo", "in_progress", "done", "left_for_handler"]


def listing(claims: list[dict[str, Any]]) -> str:
    keys = ("claim_id", "claim_type", "summary", "amount_claimed", "submitted_on")
    return json.dumps([{key: claim[key] for key in keys} for claim in claims])


def queue_tools(run_id: int, claim_llm: BaseChatModel | None) -> list[BaseTool]:
    """The queue agent's tools, for one run."""

    @tool
    def list_waiting_claims() -> str:
        """List the claims waiting in the queue: id, type, summary, amount and date."""
        claims = request("GET", "/api/claims").json()
        return listing([c for c in claims if c["status"] == "waiting"])

    @tool
    def write_todos(todos: list[TodoItem]) -> str:
        """Write the whole to-do list for the run, replacing the last one.

        Each item has its text and a status: todo, in_progress, done or
        left_for_handler.
        """
        body = {"todos": [todo.model_dump() for todo in todos]}
        response = request("PUT", f"/api/runs/{run_id}/todos", body)
        return "Saved." if response.is_success else failure(response)

    @tool
    def work_claim(claim_id: str) -> str:
        """Hand one waiting claim to a claim agent and get one line on the result."""
        taken = request("POST", f"/api/runs/{run_id}/claims/{claim_id}")
        if not taken.is_success:
            return failure(taken)
        request("POST", f"/api/claims/{claim_id}/start").raise_for_status()
        return claim_agent.work(claim_id, uuid.uuid4().hex, claim_llm)

    @tool
    def check_queue() -> str:
        """List the waiting claims this run could still take, if it missed any."""
        missed = request("GET", f"/api/runs/{run_id}/missed").json()
        return listing(missed) if missed else "No waiting claim has been missed."

    return [list_waiting_claims, write_todos, work_claim, check_queue]


def missed_claims_hook(run_id: int):
    """Send the agent back to work if it tries to finish with claims still to take."""
    nudges = 0

    @after_model(can_jump_to=["model"])
    def check_before_finishing(state: AgentState, runtime: Runtime):
        nonlocal nudges
        last = state["messages"][-1]
        if not isinstance(last, AIMessage) or last.tool_calls or nudges >= NUDGES:
            return None
        missed = request("GET", f"/api/runs/{run_id}/missed").json()
        if not missed:
            return None
        nudges += 1
        note = (
            f"You have not finished. These claims are still waiting: {listing(missed)}"
        )
        return {"messages": [HumanMessage(note)], "jump_to": "model"}

    return check_before_finishing


def queue_run(
    run_id: int,
    limit: int,
    thread_id: str,
    llm: BaseChatModel | None = None,
    claim_llm: BaseChatModel | None = None,
) -> str:
    """Run the queue agent on a started run, close the run and return its summary."""
    instructions = request("GET", "/api/instructions").json()["queue"]
    agent = create_agent(
        llm or harness.model(),
        tools=queue_tools(run_id, claim_llm),
        system_prompt=instructions,
        middleware=[*harness.middleware(CALL_LIMIT), missed_claims_hook(run_id)],
    )
    prompt = f"Work the queue. You may work at most {limit} claims."
    try:
        summary = harness.stream(agent, prompt, thread_id, lambda message: None)
    except Exception as error:
        problem = f"The run failed: {type(error).__name__}: {error}"
        finish(run_id, problem, "failed")
        raise
    finish(run_id, summary, "finished")
    return summary


def finish(run_id: int, summary: str, status: str) -> None:
    body = {"summary": summary, "status": status}
    request("POST", f"/api/runs/{run_id}/finish", body).raise_for_status()
