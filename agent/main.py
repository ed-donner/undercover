"""Public entry point for a fresh, claim-scoped helper."""

from langchain_core.language_models import BaseChatModel

from agent import api, claims, harness
from agent.context import RunContext
from agent.middleware import claim_middleware
from agent.tools import CLAIM_TOOLS


def run(claim_id: str, thread_id: str, llm: BaseChatModel | None = None) -> str:
    with api.connect() as backend:
        attempt = claims.active_attempt(backend, claim_id, thread_id)
        run_id = attempt["run_id"]
        spec = harness.AgentSpec(
            backend.instructions("claim"),
            CLAIM_TOOLS,
            claim_middleware(lambda activity: backend.event(run_id, activity)),
            80,
        )
        result = harness.invoke(
            spec,
            RunContext(backend, run_id, claim_id),
            thread_id,
            f"Process claim {claim_id}.",
            llm,
        )
        claims.verify_completion(backend, claim_id, run_id)
        return result
