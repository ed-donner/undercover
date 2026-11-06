"""The queue agent, which works the queue by handing each claim to a claim agent."""

import json
import threading
from dataclasses import dataclass, field
from typing import Any, Literal, TypedDict

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool, tool

from agent import claim_agent, common

CLAIM_FIELDS_FOR_THE_MODEL = (
    "claim_id",
    "claim_type",
    "summary",
    "submitted_on",
    "amount_claimed",
    "attempts",
)
MODEL_CALLS_PER_RUN = 10
MODEL_CALLS_PER_CLAIM = 4


class Todo(TypedDict):
    """One item on the to-do list."""

    content: str
    status: Literal["to_do", "in_progress", "done", "left_for_handler"]


@dataclass
class Run:
    """One run on the queue: what it may work, and the claims it has started."""

    run_id: int
    cap: int | None
    named: list[str]
    started: set[str] = field(default_factory=set)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def waiting(self) -> list[dict[str, Any]]:
        """Return the waiting claims this run could work."""
        claims = common.call("GET", "/api/claims").raise_for_status().json()
        return [
            claim
            for claim in claims
            if claim["status"] == "waiting"
            and (not self.named or claim["claim_id"] in self.named)
        ]

    def room(self) -> int | None:
        """Return how many more claims this run may start, or None for no cap."""
        return None if self.cap is None else self.cap - len(self.started)

    def refusal(self, claim_id: str) -> str | None:
        """Say why this run may not work a claim, if it may not."""
        if self.named and claim_id not in self.named:
            return f"{claim_id} isn't one of the claims named for this run."
        room = self.room()
        if claim_id not in self.started and room is not None and room < 1:
            return (
                f"This run is capped at {self.cap} claims and has started"
                f" {len(self.started)}, so leave {claim_id} waiting."
            )
        return None

    def missed(self) -> str | None:
        """Say which waiting claims the run could still work, if any."""
        waiting = [claim["claim_id"] for claim in self.waiting()]
        retries = [claim_id for claim_id in waiting if claim_id in self.started]
        new = [claim_id for claim_id in waiting if claim_id not in self.started]
        room = self.room()
        room = len(new) if room is None else min(room, len(new))
        if not retries and room < 1:
            return None
        reminder = ["Before you finish, there's work left in this run."]
        if retries:
            reminder.append(
                f"These claims failed once and are waiting for another try:"
                f" {', '.join(retries)}."
            )
        if room > 0:
            reminder.append(
                f"The run can start {room} more of these waiting claims:"
                f" {', '.join(new)}."
            )
        reminder.append("Work them, then finish with your summary.")
        return " ".join(reminder)

    def work(self, claim_id: str) -> str:
        """Hand one claim to a claim agent, one claim at a time."""
        with self.lock:
            refusal = self.refusal(claim_id) or claim_agent.start(claim_id)
            if refusal:
                return refusal
            self.started.add(claim_id)
            return claim_agent.attempt(claim_id)


def tools(queue: Run) -> list[BaseTool]:
    """Return the queue agent's tools for one run."""

    @tool
    def list_waiting_claims() -> str:
        """List the waiting claims this run can work, with what each is about."""
        return json.dumps(
            [
                {key: claim[key] for key in CLAIM_FIELDS_FOR_THE_MODEL}
                for claim in queue.waiting()
            ]
        )

    @tool
    def write_todos(todos: list[Todo]) -> str:
        """Save your whole to-do list for the run, replacing the last one."""
        body = {"todos": todos}
        response = common.call("PUT", f"/api/runs/{queue.run_id}/todos", body)
        return response.text if response.is_error else "Saved the to-do list."

    @tool
    def work_claim(claim_id: str) -> str:
        """Hand a claim to a claim agent, which works it and reports back in a line."""
        line = queue.work(claim_id)
        print(line, flush=True)
        return line

    return [list_waiting_claims, write_todos, work_claim]


def task(cap: int | None, claim_ids: list[str]) -> str:
    """Say what this run is to work."""
    if claim_ids:
        return f"Work these claims: {', '.join(claim_ids)}."
    if cap is None:
        return "Work every waiting claim in the queue."
    return f"Work the waiting claims in the queue, up to {cap} claims."


def run(cap: int | None, claim_ids: list[str], llm: BaseChatModel | None = None) -> str:
    """Work the queue, or the claims named, and return the summary for the handlers."""
    started = common.call("POST", "/api/runs").raise_for_status().json()
    queue = Run(started["run_id"], cap, claim_ids)
    waiting = len(queue.waiting())
    if not waiting:
        summary = "No claims are waiting."
        finish(queue.run_id, summary)
        return summary
    instructions = common.call("GET", "/api/instructions").raise_for_status().json()
    claims = waiting if cap is None else min(cap, waiting)
    agent = create_agent(
        llm or common.model(),
        tools=tools(queue),
        system_prompt=instructions["queue"],
        middleware=common.harness(
            MODEL_CALLS_PER_RUN + MODEL_CALLS_PER_CLAIM * claims, queue.missed
        ),
    )
    try:
        result = agent.invoke(
            {"messages": [{"role": "user", "content": task(cap, claim_ids)}]}
        )
    except Exception as error:
        finish(queue.run_id, f"The run stopped: {common.describe(error)}.")
        raise
    summary = result["messages"][-1].text or "The run finished without a summary."
    finish(queue.run_id, summary)
    return summary


def finish(run_id: int, summary: str) -> None:
    """Record the summary that finishes a run."""
    common.call(
        "POST", f"/api/runs/{run_id}/finish", {"summary": summary}
    ).raise_for_status()
