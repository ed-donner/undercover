"""What each kind of agent run knows, handed to its tools through `ToolRuntime`."""

from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class ClaimContext:
    """The claim an agent is deciding."""

    claim_id: str


@dataclass
class RunContext:
    """The queue run an orchestrator is working, and how it decides one claim."""

    run_id: int
    decide: Callable[[str], str]
