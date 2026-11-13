"""Invocation-scoped dependencies and graph state, never model-supplied IDs."""

from dataclasses import dataclass
from typing import NotRequired

from langchain.agents import AgentState

from agent.api import BackendAPI


@dataclass(frozen=True)
class RunContext:
    api: BackendAPI
    run_id: str
    claim_id: str | None = None


class RunState(AgentState):
    context_read: NotRequired[bool]
