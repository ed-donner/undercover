"""What both agents share: the backend, the model and the retries."""

import json
import os
from typing import Any

import httpx
from dotenv import load_dotenv
from langchain.agents.middleware import (
    AgentMiddleware,
    ModelRetryMiddleware,
    ToolRetryMiddleware,
)
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

load_dotenv(override=True)

BACKEND_URL = "http://localhost:8000"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "deepseek/deepseek-v4.1-flash"
MODEL_TIMEOUT = 60
RETRY_DELAY = 1.0


def backend() -> httpx.Client:
    """Return a client for the UnderCover backend."""
    return httpx.Client(base_url=BACKEND_URL, timeout=30)


def request(
    method: str, path: str, body: dict[str, Any] | None = None
) -> httpx.Response:
    """Call the backend and return its response."""
    with backend() as client:
        return client.request(method, path, json=body)


def call(method: str, path: str, body: dict[str, Any] | None = None) -> str:
    """Call the backend for a tool, returning a refusal as text rather than raising."""
    response = request(method, path, body)
    if response.is_client_error:
        return f"Refused: {response.json()['detail']}"
    response.raise_for_status()
    return response.text


def api(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
    """Call the backend for the runner, raising on any refusal or error."""
    response = request(method, path, body)
    response.raise_for_status()
    return response.json()


def instructions(name: str) -> str:
    """Fetch one set of the agent's instructions, queue or claim, from the backend."""
    return json.loads(call("GET", "/api/instructions"))[name]


def model() -> ChatOpenAI:
    """Return the model named in MODEL_NAME, or DeepSeek V4.1 Flash by default."""
    name = os.getenv("MODEL_NAME")
    return ChatOpenAI(
        model=name or DEFAULT_MODEL,
        base_url=OPENROUTER_BASE_URL,
        api_key=SecretStr(os.environ["OPENROUTER_API_KEY"]),
        timeout=MODEL_TIMEOUT,
        extra_body=None if name else {"reasoning": {"effort": "low"}},
    )


def retries() -> list[AgentMiddleware[Any, Any, Any]]:
    """Retry errors from the model provider and tool calls that fail to reach us."""
    return [
        ModelRetryMiddleware(
            max_retries=2, on_failure="error", initial_delay=RETRY_DELAY
        ),
        ToolRetryMiddleware(max_retries=2, initial_delay=RETRY_DELAY),
    ]
