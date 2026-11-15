"""The UnderCover Agent."""

import argparse
import json
import uuid

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel

from agent.base import call, model
from agent.tools import instructions, queue_tools, work_claim

QUEUE_RECURSION_LIMIT = 1000


def start_run(limit: int) -> int:
    """Start a run in the backend and return its id."""
    return json.loads(call("POST", "/api/runs", {"limit": limit}))["id"]


def waiting(run_id: int) -> list[str]:
    """Return the claims the run may still work."""
    return [
        c["claim_id"] for c in json.loads(call("GET", f"/api/runs/{run_id}/waiting"))
    ]


def run(claim_id: str, thread_id: str, llm: BaseChatModel | None = None) -> str:
    """Work one named claim in a run of its own and return its result."""
    run_id = start_run(1)
    items = [{"text": claim_id, "status": "in_progress"}]
    call("PUT", f"/api/runs/{run_id}/todos", {"items": items})
    line = work_claim(run_id, claim_id, llm or model(), thread_id)
    status = json.loads(call("GET", f"/api/claims/{claim_id}"))["status"]
    items[0]["status"] = {"waiting": "todo", "for_handler": "for_handler"}.get(
        status, "done"
    )
    call("PUT", f"/api/runs/{run_id}/todos", {"items": items})
    call("POST", f"/api/runs/{run_id}/summary", {"summary": line})
    return line


def run_queue(limit: int, thread_id: str, llm: BaseChatModel | None = None) -> str:
    """Work the waiting claims, at most limit of them, and return the summary."""
    llm = llm or model()
    run_id = start_run(limit)
    agent = create_agent(
        llm,
        tools=queue_tools(run_id, llm, thread_id),
        system_prompt=instructions()["queue"],
    )
    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": QUEUE_RECURSION_LIMIT,
    }
    request = f"Run {run_id}: work the queue, at most {limit} claims."
    messages = [{"role": "user", "content": request}]
    result = agent.invoke({"messages": messages}, config=config)  # type: ignore[arg-type]
    missed = waiting(run_id)
    if missed:
        nudge = (
            f"These claims are still waiting and within the cap: {', '.join(missed)}."
        )
        result = agent.invoke(
            {"messages": [*result["messages"], {"role": "user", "content": nudge}]},
            config=config,  # type: ignore[arg-type]
        )
        missed = waiting(run_id)
    summary = result["messages"][-1].text
    if missed:
        summary += f"\n\nNot worked: {', '.join(missed)}."
    call("POST", f"/api/runs/{run_id}/summary", {"summary": summary})
    return summary


def cli() -> None:
    """Run the agent from the command line."""
    parser = argparse.ArgumentParser(description="Run the UnderCover Agent.")
    parser.add_argument("--limit", type=int, help="work at most this many claims")
    parser.add_argument("--claim", help="work one named claim")
    args = parser.parse_args()
    thread_id = f"run-{uuid.uuid4().hex[:8]}"
    if args.claim:
        print(run(args.claim, thread_id))
        return
    limit = args.limit or len(json.loads(call("GET", "/api/claims")))
    print(run_queue(limit, thread_id))
