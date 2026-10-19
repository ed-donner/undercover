"""What both agents share: the backend, the model, the middleware and the steps."""

import os
from collections.abc import Callable
from typing import Any

import httpx
from dotenv import load_dotenv
from langchain.agents.middleware import (
    AgentMiddleware,
    ModelCallLimitMiddleware,
    ModelRetryMiddleware,
    ToolRetryMiddleware,
)
from langchain_core.messages import AIMessage, AnyMessage
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

load_dotenv(override=True)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "deepseek/deepseek-v4.1-flash"
MODEL_TIMEOUT = 120
RETRIES = 2
RETRY_DELAY = 1.0


def backend() -> httpx.Client:
    """Return a client for the UnderCover backend."""
    return httpx.Client(
        base_url=os.getenv("BACKEND_URL", "http://localhost:8000"), timeout=30
    )


def request(method: str, path: str, body: dict[str, Any] | None = None):
    with backend() as client:
        return client.request(method, path, json=body)


def failure(response: httpx.Response) -> str:
    return f"Error {response.status_code}: {response.json()['detail']}"


def reply(method: str, path: str, body: dict[str, Any] | None = None) -> str:
    """Return the backend's reply, or its error, for the model to read."""
    response = request(method, path, body)
    return response.text if response.is_success else failure(response)


def model() -> ChatOpenAI:
    """Return the model named in MODEL_NAME, or DeepSeek V4.1 Flash by default."""
    name = os.getenv("MODEL_NAME")
    return ChatOpenAI(
        model=name or DEFAULT_MODEL,
        base_url=OPENROUTER_BASE_URL,
        api_key=SecretStr(os.environ["OPENROUTER_API_KEY"]),
        reasoning_effort=None if name else "low",
        timeout=MODEL_TIMEOUT,
        max_retries=0,
    )


def middleware(call_limit: int) -> list[AgentMiddleware[Any, Any, Any]]:
    """Retry model and tool calls, and stop an agent that keeps calling the model."""
    return [
        ModelRetryMiddleware(
            max_retries=RETRIES, on_failure="error", initial_delay=RETRY_DELAY
        ),
        ToolRetryMiddleware(
            max_retries=RETRIES, on_failure="error", initial_delay=RETRY_DELAY
        ),
        ModelCallLimitMiddleware(run_limit=call_limit, exit_behavior="end"),
    ]


def stream(agent, prompt: str, thread_id: str, seen: Callable[[AnyMessage], None]):
    """Run an agent, show each message to `seen` and return its final reply."""
    final = ""
    for update in agent.stream(
        {"messages": [{"role": "user", "content": prompt}]},
        config={"configurable": {"thread_id": thread_id}},
        stream_mode="updates",
    ):
        for output in update.values():
            for message in (output or {}).get("messages", []):
                seen(message)
                if isinstance(message, AIMessage) and not message.tool_calls:
                    final = message.text
    return final
