"""All model-visible tools; dependencies are injected by LangChain runtime."""

import json
from typing import Literal

from langchain.tools import ToolRuntime, tool
from langchain_core.messages import ToolMessage
from langgraph.types import Command
from pydantic import BaseModel

from agent import claims, delegation
from agent.context import RunContext, RunState

Runtime = ToolRuntime[RunContext, RunState]


class DecisionDraft(BaseModel):
    outcome: Literal["approve", "decline", "refer"]
    payout: str
    calculation: str
    explanation: str
    policy_sections: list[int]
    manual_sections: list[int]
    manual_version: str


class PlannedTask(BaseModel):
    claim_id: str
    state: Literal["todo", "in_progress", "done", "needs_handler"]


def claim_id(runtime: Runtime) -> str:
    if runtime.context.claim_id is None:
        raise RuntimeError("This tool requires a claim-scoped invocation")
    return runtime.context.claim_id


@tool
def read_context(runtime: Runtime) -> Command:
    """Read the selected claim's full evidence, policy, plan and customer history."""
    ctx = runtime.context
    ctx.api.event(ctx.run_id, "context_started")
    result = claims.context(ctx.api, claim_id(runtime))
    ctx.api.event(ctx.run_id, "context_read")
    return Command(
        update={
            "context_read": True,
            "messages": [
                ToolMessage(
                    content=json.dumps(result), tool_call_id=runtime.tool_call_id or ""
                )
            ],
        }
    )


@tool
def list_sections(runtime: Runtime) -> str:
    """List section titles and versions of the wording and claims manual."""
    return json.dumps(runtime.context.api.sections())


@tool
def search_sections(document_id: str, query: str, runtime: Runtime) -> str:
    """Search wording or manual sections and return short excerpts."""
    return json.dumps(runtime.context.api.search_sections(document_id, query))


@tool
def read_section(document_id: str, section: int, runtime: Runtime) -> str:
    """Read and audit a complete numbered wording or manual section."""
    ctx = runtime.context
    return json.dumps(
        ctx.api.read_section(claim_id(runtime), ctx.run_id, document_id, section)
    )


@tool
def record_decision(decision: DecisionDraft, runtime: Runtime) -> str:
    """Record a claim decision with its calculation and read source references."""
    if not runtime.state.get("context_read", False):
        raise RuntimeError("Read context before deciding")
    ctx = runtime.context
    ctx.api.event(ctx.run_id, "decision_started")
    return json.dumps(
        claims.decide(ctx.api, claim_id(runtime), ctx.run_id, decision.model_dump())
    )


@tool
def request_payment(amount: str, runtime: Runtime) -> str:
    """Request exact-amount simulated payment; handler sign-off may block it."""
    ctx = runtime.context
    ctx.api.event(ctx.run_id, "payment_started")
    return json.dumps(claims.pay(ctx.api, claim_id(runtime), ctx.run_id, amount))


@tool
def read_queue(runtime: Runtime) -> str:
    """Read scope, cap, persisted tasks and lightweight claim metadata."""
    ctx = runtime.context
    return json.dumps(delegation.queue_context(ctx.api, ctx.run_id))


@tool
def write_todos(tasks: list[PlannedTask], runtime: Runtime) -> str:
    """Persist ordered tasks using recorded states and todo for new work."""
    ctx = runtime.context
    return json.dumps(ctx.api.write_todos(ctx.run_id, [t.model_dump() for t in tasks]))


@tool
def delegate_claim(claim_id: str, runtime: Runtime) -> str:
    """Delegate one planned claim to a fresh helper and return a result line."""
    ctx = runtime.context
    return delegation.delegate(ctx.api, ctx.run_id, claim_id)


@tool
def check_completion(runtime: Runtime) -> str:
    """Find unfinished or missed work within this run's cap."""
    ctx = runtime.context
    return json.dumps(ctx.api.check_run(ctx.run_id))


@tool(return_direct=True)
def finish_run(runtime: Runtime) -> str:
    """Finalize a checked run and return its verified summary."""
    ctx = runtime.context
    return ctx.api.finish_run(ctx.run_id)["summary"]


CLAIM_TOOLS = [
    read_context,
    list_sections,
    search_sections,
    read_section,
    record_decision,
    request_payment,
]
QUEUE_TOOLS = [read_queue, write_todos, delegate_claim, check_completion, finish_run]
