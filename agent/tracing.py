"""Tracing in Langfuse: the one module that knows about it.

Without Langfuse keys in the environment nothing is traced.
"""

import os

from langchain_core.runnables import RunnableConfig
from langfuse import get_client
from langfuse.langchain import CallbackHandler


def enabled() -> bool:
    """Say whether Langfuse keys are set."""
    return bool(os.getenv("LANGFUSE_SECRET_KEY"))


def trace_config(session_id: str) -> RunnableConfig:
    """Return the run config that traces into one Langfuse session."""
    if not enabled():
        return {}
    return {
        "callbacks": [CallbackHandler()],
        "metadata": {"langfuse_session_id": session_id},
    }


def flush() -> None:
    """Send any traces still waiting, before a short-lived process ends."""
    if enabled():
        get_client().flush()
