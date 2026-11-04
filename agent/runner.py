"""The UnderCover Agent: a queue runner that hands each claim to a fresh subagent."""

from typing import Any, Literal

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel

from agent.client import call
from agent.model import model
from agent.tools import claim_tools, step_recorder, text

NO_CAP = 1000
CLAIM_STEP_LIMIT = 60
RUNNER_STEP_LIMIT = 200
MAX_ROUNDS = 4
OUTCOMES = {"decline": "declined", "refer": "referred"}


class Todo(BaseModel):
    """One item of the agent's to-do list."""

    claim_id: str
    text: str
    state: Literal["todo", "in_progress", "done", "left_for_handler"]


def line(claim_id: str) -> str:
    """Summarize a worked claim in one line, from what the backend recorded."""
    claim = call("GET", f"/api/claims/{claim_id}")
    decision = claim["decision"]
    if decision is None:
        return f"{claim_id}: no decision, status {claim['status']}"
    if decision["decision"] != "approve":
        return f"{claim_id}: {OUTCOMES[decision['decision']]}"
    payout = f"approved ${decision['payout']:.2f}"
    if claim["payment"]:
        return f"{claim_id}: {payout}, paid"
    if claim["status"] == "awaiting_signoff":
        return f"{claim_id}: {payout}, payment waits for a handler's sign-off"
    return f"{claim_id}: {payout}, not paid"


def fail(claim_id: str, reason: str) -> str:
    """Record a failure and say whether the claim is retried or left for a handler."""
    status = call("POST", f"/api/claims/{claim_id}/failure", {"reason": reason})[
        "status"
    ]
    if status == "waiting":
        return f"{claim_id}: FAILED ({reason}); back in the queue to try again"
    return f"{claim_id}: FAILED ({reason}); failed twice, left for a handler"


def work(run_id: int, claim_id: str, llm: BaseChatModel, claim_prompt: str) -> str:
    """Work one claim with a fresh subagent and report back in one line."""
    started = call("POST", f"/api/runs/{run_id}/claims/{claim_id}/start")
    if "error" in started:
        return f"{claim_id}: not started, {started['detail']}"
    subagent = create_agent(
        llm,
        tools=claim_tools(claim_id),
        system_prompt=claim_prompt,
        middleware=[step_recorder(claim_id)],
    )
    try:
        subagent.invoke(
            {"messages": [{"role": "user", "content": f"Work claim {claim_id}."}]},
            config={"recursion_limit": CLAIM_STEP_LIMIT},
        )
    except Exception as error:
        return fail(claim_id, f"{type(error).__name__}: {error}")
    if call("GET", f"/api/claims/{claim_id}")["decision"] is None:
        return fail(claim_id, "the subagent ended without a decision")
    return line(claim_id)


def queue_tools(run_id: int, llm: BaseChatModel, claim_prompt: str) -> list[BaseTool]:
    """Return the queue runner's tools for one run."""

    @tool
    def list_waiting_claims() -> str:
        """List the waiting claims, the run's cap and the claims already worked."""
        return text(call("GET", f"/api/runs/{run_id}/waiting"))

    @tool
    def write_todos(items: list[Todo]) -> str:
        """Replace the to-do list with these items; send the whole list each time."""
        body = {"items": [item.model_dump() for item in items]}
        return text(call("PUT", f"/api/runs/{run_id}/todos", body))

    @tool
    def work_claim(claim_id: str) -> str:
        """Give one claim to a fresh subagent; returns one line with the outcome."""
        return work(run_id, claim_id, llm, claim_prompt)

    @tool
    def check_missed() -> str:
        """List the waiting claims within the cap that the run has not finished."""
        return text(call("GET", f"/api/runs/{run_id}/missed"))

    return [list_waiting_claims, write_todos, work_claim, check_missed]


def drive(run_id: int, task: str, llm: BaseChatModel, prompts: dict[str, str]) -> str:
    """Run the queue runner until nothing within the cap is missed."""
    runner = create_agent(
        llm,
        tools=queue_tools(run_id, llm, prompts["claim"]),
        system_prompt=prompts["queue_runner"],
    )
    start = {"role": "user", "content": task}
    messages: list[Any] = [start]
    summary = ""
    for _ in range(MAX_ROUNDS):
        try:
            result = runner.invoke(
                {"messages": messages}, config={"recursion_limit": RUNNER_STEP_LIMIT}
            )
        except Exception as error:
            summary = f"The queue runner stopped: {type(error).__name__}: {error}"
            resume = (
                "Your last attempt stopped with an error. Carry on: the claims "
                "already worked are in list_waiting_claims."
            )
            messages = [start, {"role": "user", "content": resume}]
            continue
        summary = result["messages"][-1].text
        missed = call("GET", f"/api/runs/{run_id}/missed")["missed"]
        if not missed:
            return summary
        nudge = (
            "You have not finished. These claims are still waiting within the cap: "
            f"{', '.join(missed)}. Work them, check again, then give the summary."
        )
        messages = [*result["messages"], {"role": "user", "content": nudge}]
    return summary


def run(
    cap: int | None = None, claim_id: str = "", llm: BaseChatModel | None = None
) -> str:
    """Run the agent on the queue, up to a cap, or on one named claim."""
    llm = llm or model()
    prompts = call("GET", "/api/instructions")
    if claim_id:
        started = call("POST", "/api/runs/claim", {"claim_id": claim_id})
        task = f"Run {started['run_id']} is for claim {claim_id} only. The cap is 1."
    else:
        started = call("POST", "/api/runs", {"cap": cap or NO_CAP})
        task = f"Run {started['run_id']}. The cap is {cap or NO_CAP} claims."
    summary = drive(started["run_id"], task, llm, prompts)
    call("POST", f"/api/runs/{started['run_id']}/finish", {"summary": summary})
    return summary
