"""The UnderCover Agent: decides one claim, or works the whole queue."""

from langchain_core.language_models import BaseChatModel

from agent import api, tracing
from agent.harness import AgentSpec, run_agent
from agent.tools import CLAIM_TOOLS, QUEUE_TOOLS, ClaimContext, RunContext


def decide_claim(claim_id: str, llm: BaseChatModel | None = None) -> str:
    """Decide one claim from a clean start, and return the agent's final reply."""
    reply = run_agent(
        AgentSpec(api.claim_instructions(), CLAIM_TOOLS),
        ClaimContext(claim_id),
        f"Decide claim {claim_id}.",
        llm,
        tracing.trace_config(claim_id),
    )
    tracing.flush()
    return reply


def run_queue(cap: int | None = None, llm: BaseChatModel | None = None) -> str:
    """Work the waiting claims (the first `cap` of them, if capped) as one run."""
    waiting = [c["claim_id"] for c in api.list_claims() if c["status"] == "waiting"]
    run_id = api.start_run(waiting[:cap])
    reply = run_agent(
        AgentSpec(api.queue_instructions(), QUEUE_TOOLS),
        RunContext(run_id, decide_claim),
        "Work the claims queue.",
        llm,
        tracing.trace_config(f"run-{run_id}"),
    )
    tracing.flush()
    return reply
