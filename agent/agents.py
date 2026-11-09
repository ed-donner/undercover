"""The UnderCover Agent: decides one claim, or works the whole queue."""

from contextvars import Context
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.types import Command

from agent import api, checkpoint, tracing
from agent.claim_graph import build_graph
from agent.claim_state import new_claim
from agent.harness import AgentSpec, model, run_agent
from agent.tools import QUEUE_TOOLS, ClaimContext, RunContext


def decide_claim(
    claim_id: str,
    llm: BaseChatModel | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
) -> str:
    """Work a claim through its graph: from the start, or from where it stopped.

    It runs in a fresh context, so a claim worked inside a queue run shares
    neither the queue agent's callbacks nor its trace with it.

    A claim waiting at its sign-off carries on only once a handler has signed off.
    """
    claim = api.get_claim(claim_id)
    thread_id = f"{claim_id}-{claim['thread']}"
    graph = build_graph(
        checkpointer or checkpoint.saver(), llm or model(), api.claim_instructions()
    )
    return Context().run(_work_traced, graph, claim, thread_id)


def _work_traced(graph: Any, claim: dict[str, Any], thread_id: str) -> str:
    """Work a claim in a trace of its own, in one Langfuse session."""
    with tracing.trace(thread_id) as traced:
        config: RunnableConfig = {**traced, "configurable": {"thread_id": thread_id}}
        return _work(graph, config, claim)


def _work(graph: Any, config: RunnableConfig, claim: dict[str, Any]) -> str:
    """Start the claim's graph, carry it on, or answer a sign-off."""
    claim_id = claim["claim_id"]
    state = graph.get_state(config)
    if state.values and not state.next:
        return state.values["messages"][-1].text
    if state.next == ("approval",):
        if claim["signed_off_by"] is None:
            return f"{claim_id} is waiting for a handler to sign off."
        start = Command(resume={"handler": claim["signed_off_by"]})
    else:
        start = None if state.next else new_claim(claim_id)
    context = ClaimContext(claim_id)
    result = graph.invoke(start, config, context=context, durability="sync")
    return result["messages"][-1].text


def carry_on(
    llm: BaseChatModel | None = None, checkpointer: BaseCheckpointSaver | None = None
) -> None:
    """Carry on with claims stopped or signed off while the agent was away.

    Claims on an unfinished run are left to that run, which keeps their attempts.
    """
    run = api.get_unfinished_run()
    on_the_run = {item["claim_id"] for item in run["items"]} if run else set()
    for claim_id in api.list_unfinished_claims():
        if claim_id not in on_the_run:
            decide_claim(claim_id, llm, checkpointer)


def run_queue(cap: int | None = None, llm: BaseChatModel | None = None) -> str:
    """Work the waiting claims (the first `cap` of them, if capped) as one run.

    An unfinished run is finished first, and it keeps its own list of claims.
    """
    carry_on()
    run = api.get_unfinished_run()
    if run:
        run_id = run["run_id"]
    else:
        waiting = [
            c["claim_id"] for c in api.list_claims() if c["status"] == api.WAITING
        ]
        run_id = api.start_run(waiting[:cap])
    with tracing.trace(f"run-{run_id}") as config:
        return run_agent(
            AgentSpec(api.queue_instructions(), QUEUE_TOOLS),
            RunContext(run_id, decide_claim),
            "Work the claims queue.",
            llm,
            config,
        )
