"""The queue agent: it plans a run as a to-do list and hands out each claim."""

import json
import threading
from dataclasses import dataclass, field
from typing import Any, Literal, TypedDict

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool, tool

from agent import claim
from agent.common import api, call, instructions, model, retries

RECURSION_LIMIT = 1000
CLAIM_FIELDS = ["claim_id", "claim_type", "summary", "amount_claimed", "attempts"]


class Todo(TypedDict):
    """One item on the to-do list."""

    claim_id: str
    content: str
    status: Literal["todo", "in_progress", "done", "handler"]


@dataclass
class Run:
    """A run in progress: its scope, its cap and the claims it has worked."""

    id: int
    claim_id: str | None
    cap: int
    llm: BaseChatModel
    worked: list[str] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)


def waiting(run: Run) -> list[dict[str, Any]]:
    """Return the waiting claims in the run's scope."""
    return [
        c
        for c in api("GET", "/api/claims")
        if c["status"] == "waiting" and run.claim_id in (None, c["claim_id"])
    ]


def missed(run: Run) -> list[str]:
    """Return the waiting claims the run should still work: retries, then new ones."""
    left = run.cap - len(run.worked)
    found = []
    for c in waiting(run):
        if c["claim_id"] in run.worked:
            found.append(c["claim_id"])
        elif left > 0:
            found.append(c["claim_id"])
            left -= 1
    return found


def tools(run: Run) -> list[BaseTool]:
    """Return the queue agent's tools, bound to this run."""

    @tool
    def list_waiting_claims() -> str:
        """List the waiting claims in this run and how many more the cap allows."""
        claims = [{key: c[key] for key in CLAIM_FIELDS} for c in waiting(run)]
        return json.dumps(
            {
                "cap": run.cap,
                "worked_so_far": run.worked,
                "new_claims_left": run.cap - len(run.worked),
                "claims": claims,
            }
        )

    @tool
    def write_todos(todos: list[Todo]) -> str:
        """Replace the run's to-do list: one item for each claim you plan to work."""
        return call("POST", f"/api/runs/{run.id}/todos", {"todos": todos})

    @tool
    def work_claim(claim_id: str) -> str:
        """Hand one waiting claim to a fresh claim agent and get its outcome."""
        with run.lock:
            if run.claim_id not in (None, claim_id):
                return f"Refused: this run is for {run.claim_id} only"
            if claim_id not in run.worked and len(run.worked) >= run.cap:
                return f"Refused: the run has already worked its cap of {run.cap}"
            line = claim.work_claim(claim_id, run.llm)
            if not line.startswith("Refused") and claim_id not in run.worked:
                run.worked.append(claim_id)
            return line

    @tool
    def finish_run(summary: str) -> str:
        """Finish the run with a short summary for the handlers."""
        unworked = missed(run)
        if unworked:
            return (
                f"Refused: {', '.join(unworked)} still waiting within the run. "
                "Work them before you finish."
            )
        return call("POST", f"/api/runs/{run.id}/finish", {"summary": summary})

    return [list_waiting_claims, write_todos, work_claim, finish_run]


def work_queue(run_id: int, llm: BaseChatModel) -> None:
    """Let the queue agent work the run, finishing it if the agent did not."""
    record = api("GET", f"/api/runs/{run_id}")
    run = Run(run_id, record["claim_id"], record["cap"], llm)
    agent = create_agent(
        llm,
        tools=tools(run),
        system_prompt=instructions("queue"),
        middleware=retries(),
    )
    scope = (
        f"claim {run.claim_id} only"
        if run.claim_id
        else f"the waiting claims, up to {run.cap} of them"
    )
    agent.invoke(
        {"messages": [{"role": "user", "content": f"Please work {scope}."}]},
        config={"recursion_limit": RECURSION_LIMIT},
    )
    if api("GET", f"/api/runs/{run_id}")["status"] == "running":
        api(
            "POST",
            f"/api/runs/{run_id}/finish",
            {"summary": "The agent stopped without writing a summary."},
        )


def run_queue(run_id: int, llm: BaseChatModel | None = None) -> None:
    """Run the queue agent; if it fails, release its claims and fail the run."""
    try:
        work_queue(run_id, llm or model())
    except Exception as error:
        for c in api("GET", "/api/claims"):
            if c["status"] == "in_progress":
                api(
                    "POST",
                    f"/api/claims/{c['claim_id']}/release",
                    {"problem": f"The run stopped with an error: {error}"},
                )
        api(
            "POST",
            f"/api/runs/{run_id}/fail",
            {"problem": f"The run stopped with an error: {error}"},
        )
