"""Bounded retries and public activity, without exposing model messages."""

from collections.abc import Callable
from http import HTTPStatus

import httpx
from langchain.agents.middleware import (
    AgentMiddleware,
    ModelRetryMiddleware,
    ToolRetryMiddleware,
)
from langchain.agents.middleware.types import (
    ModelRequest,
    ModelResponse,
    ToolCallRequest,
)
from langchain_core.messages import ToolMessage
from langgraph.types import Command
from openai import APIConnectionError, APIStatusError


def transient(error: Exception) -> bool:
    if isinstance(error, (httpx.TransportError, APIConnectionError)):
        return True
    if isinstance(error, APIStatusError):
        return (
            error.status_code == HTTPStatus.TOO_MANY_REQUESTS
            or error.status_code >= HTTPStatus.INTERNAL_SERVER_ERROR
        )
    if isinstance(error, httpx.HTTPStatusError):
        return (
            error.response.status_code == HTTPStatus.TOO_MANY_REQUESTS
            or error.response.status_code >= HTTPStatus.INTERNAL_SERVER_ERROR
        )
    return False


class PublicActivity(AgentMiddleware):
    def __init__(self, event: Callable[[str], None]):
        self.event = event

    def wrap_model_call(
        self, request: ModelRequest, handler: Callable[[ModelRequest], ModelResponse]
    ) -> ModelResponse:
        self.event("model_requested")
        return handler(request)

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command],
    ) -> ToolMessage | Command:
        self.event("tool_started")
        try:
            result = handler(request)
        except httpx.HTTPStatusError as error:
            if error.response.status_code not in (400, 404, 409, 422):
                raise
            self.event("tool_failed")
            return ToolMessage(
                content=(
                    "Backend rejected this step. Re-read state or correct "
                    "the inputs; do not repeat an invalid write."
                ),
                tool_call_id=request.tool_call["id"],
                status="error",
            )
        self.event("tool_completed")
        return result


def claim_middleware(event: Callable[[str], None]) -> list[AgentMiddleware]:
    return [
        ModelRetryMiddleware(
            max_retries=1,
            retry_on=transient,
            on_failure="error",
            initial_delay=0.2,
            jitter=False,
        ),
        PublicActivity(event),
        ToolRetryMiddleware(
            max_retries=1,
            tools=["read_context", "list_sections", "search_sections", "read_section"],
            retry_on=transient,
            on_failure="error",
            initial_delay=0.2,
            jitter=False,
        ),
    ]
