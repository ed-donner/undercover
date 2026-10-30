"""The queue orchestrator: works every claim on one run's to-do list."""

import concurrent.futures
from typing import Any

import httpx
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool, tool

from agent.main import backend, model
from agent.main import run as decide_one_claim

CLAIM_TIMEOUT_SECONDS = 180
SETTLED_CLAIM_STATUSES = {"decided", "waiting for sign-off"}


def queue_instructions() -> str:
    """Fetch the instructions for running the queue from the backend."""
    with backend() as client:
        response = client.get("/api/queue-instructions")
    response.raise_for_status()
    return response.json()["instructions"]


def _waiting_claim_ids(cap: int | None) -> list[str]:
    with backend() as client:
        response = client.get("/api/claims")
    response.raise_for_status()
    waiting = [
        claim["claim_id"] for claim in response.json() if claim["status"] == "waiting"
    ]
    return waiting[:cap] if cap is not None else waiting


def _claim_status(claim_id: str) -> str:
    with backend() as client:
        response = client.get(f"/api/claims/{claim_id}")
    response.raise_for_status()
    return response.json()["status"]


def _update_item(run_id: int, claim_id: str, status: str, note: str) -> None:
    with backend() as client:
        response = client.post(
            f"/api/runs/{run_id}/items/{claim_id}",
            json={"status": status, "note": note},
        )
    response.raise_for_status()


def _requeue(claim_id: str) -> None:
    with backend() as client:
        client.post(f"/api/claims/{claim_id}/requeue")


def _try_claim(claim_id: str) -> str:
    """Decide one claim with a fresh subagent, under a wall-clock timeout.

    A thread, not a bare call, because the per-claim agent's LLM call has no
    timeout of its own and a bad day on the model provider shouldn't hang the run.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(decide_one_claim, claim_id, f"queue-{claim_id}")
        return future.result(timeout=CLAIM_TIMEOUT_SECONDS)


def _attempt_claim(run_id: int, claim_id: str) -> tuple[bool, str]:
    """Try to decide a claim once.

    Returns (True, outcome) if settled, or (False, the error) to retry.
    """
    _update_item(run_id, claim_id, "in progress", "")
    try:
        reply = _try_claim(claim_id)
    except Exception as error:  # a failed attempt is handled, not fatal
        if _claim_status(claim_id) in SETTLED_CLAIM_STATUSES:
            return True, "Decided (the result arrived after a failed retry)."
        _requeue(claim_id)
        return False, str(error)
    return True, reply


def work_one_claim(run_id: int, claim_id: str) -> str:
    """Decide one claim, retrying once on failure, keeping its to-do item current."""
    settled, note = _attempt_claim(run_id, claim_id)
    if not settled:
        _update_item(run_id, claim_id, "to do", f"Attempt 1 failed: {note}")
        settled, note = _attempt_claim(run_id, claim_id)
    if settled:
        _update_item(run_id, claim_id, "done", note)
        return note
    note = f"Left for a handler after 2 failed attempts: {note}"
    _update_item(run_id, claim_id, "left for a handler", note)
    return note


def queue_tools(run_id: int) -> list[BaseTool]:
    """Build the tools the orchestrator uses to work one run's to-do list."""

    @tool
    def get_to_do() -> list[dict[str, Any]]:
        """List the run's claims and their to-do status."""
        with backend() as client:
            response = client.get("/api/runs/current")
        response.raise_for_status()
        return response.json()["items"]

    @tool
    def work_claim(claim_id: str) -> str:
        """Hand one claim to a fresh subagent and report what happened."""
        return work_one_claim(run_id, claim_id)

    @tool
    def finish_run(summary: str) -> str:
        """Finish the run with a short summary, once every claim is settled."""
        with backend() as client:
            response = client.post(
                f"/api/runs/{run_id}/finish", json={"summary": summary}
            )
        if response.status_code == httpx.codes.CONFLICT:
            return f"Not finished — {response.json()['detail']}"
        response.raise_for_status()
        return "Run finished."

    return [get_to_do, work_claim, finish_run]


def run_queue(cap: int | None = None, llm: BaseChatModel | None = None) -> str:
    """Start a run over the waiting claims, capped if asked, and work it through."""
    claim_ids = _waiting_claim_ids(cap)
    with backend() as client:
        response = client.post("/api/runs", json={"claim_ids": claim_ids})
    response.raise_for_status()
    run_id = response.json()["run_id"]

    agent = create_agent(
        llm or model(), tools=queue_tools(run_id), system_prompt=queue_instructions()
    )
    result = agent.invoke(
        {"messages": [{"role": "user", "content": "Work the claims queue."}]},
        config={"configurable": {"thread_id": f"queue-run-{run_id}"}},
    )
    return result["messages"][-1].text
