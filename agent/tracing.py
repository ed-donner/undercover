"""Tracing in Langfuse: the one module that knows about it.

Without Langfuse keys in the environment nothing is traced.
"""

import os
from collections.abc import Iterator
from contextlib import contextmanager

from langchain_core.runnables import RunnableConfig
from langfuse import get_client, propagate_attributes
from langfuse.langchain import CallbackHandler


def enabled() -> bool:
    """Say whether Langfuse keys are set."""
    return bool(os.getenv("LANGFUSE_SECRET_KEY"))


@contextmanager
def trace(session_id: str) -> Iterator[RunnableConfig]:
    """Trace the work inside as a trace of its own, in one Langfuse session.

    Call it with nothing else of the agent in the context, so it starts a trace
    of its own rather than joining another.
    """
    if not enabled():
        yield {}
        return
    client = get_client()
    with (
        client.start_as_current_observation(name=session_id),
        propagate_attributes(session_id=session_id),
    ):
        yield {"callbacks": [CallbackHandler()]}
    client.flush()
