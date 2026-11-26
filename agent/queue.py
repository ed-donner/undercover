"""Public entry point for queue planning and delegation."""

from langchain_core.language_models import BaseChatModel

from agent import api, harness
from agent.context import RunContext
from agent.middleware import queue_middleware
from agent.tools import QUEUE_TOOLS


def run_queue(run_id: str, thread_id: str, llm: BaseChatModel | None = None) -> str:
    with api.connect() as backend:
        state = backend.run(run_id)
        spec = harness.AgentSpec(
            backend.instructions("queue"),
            QUEUE_TOOLS,
            queue_middleware(lambda: backend.run(run_id)),
            max(40, state["max_claims"] * 16 + 20),
        )
        harness.invoke(
            spec,
            RunContext(backend, run_id),
            thread_id,
            f"Work run {run_id} to a checked completion within its scope and cap.",
            llm,
        )
        final = backend.run(run_id)
        if final["status"] != "completed":
            raise RuntimeError("Agent did not complete the checked run")
        return final["summary"]
