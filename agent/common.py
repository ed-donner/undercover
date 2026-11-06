"""What the UnderCover agents share: the backend, the model and the harness."""

import os
from collections.abc import Callable
from typing import Any

import httpx
from dotenv import load_dotenv
from langchain.agents.middleware import (
    AgentMiddleware,
    AgentState,
    ModelCallLimitMiddleware,
    ModelRetryMiddleware,
    ToolRetryMiddleware,
    hook_config,
)
from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.runtime import Runtime
from pydantic import SecretStr

load_dotenv(override=True)

BACKEND_URL = "http://localhost:8000"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "deepseek/deepseek-v4.1-flash"
MODEL_TIMEOUT_SECONDS = 120
RETRIES = 3
RETRY_DELAY_SECONDS = 1.0
MOST_REMINDERS = 2
LONGEST_ERROR = 200


def backend() -> httpx.Client:
    """Return a client for the UnderCover backend."""
    return httpx.Client(base_url=BACKEND_URL, timeout=30)


def call(
    method: str,
    url: str,
    body: dict[str, Any] | None = None,
    params: dict[str, str] | None = None,
) -> httpx.Response:
    """Call the backend and return its response, refusals included."""
    with backend() as client:
        return client.request(method, url, json=body, params=params)


def detail(response: httpx.Response) -> str:
    """Return the reason the backend gave for refusing a request."""
    return response.json()["detail"]


def model() -> ChatOpenAI:
    """Return the model named in MODEL_NAME, or DeepSeek V4.1 Flash by default."""
    name = os.getenv("MODEL_NAME")
    return ChatOpenAI(
        model=name or DEFAULT_MODEL,
        base_url=OPENROUTER_BASE_URL,
        api_key=SecretStr(os.environ["OPENROUTER_API_KEY"]),
        reasoning_effort=None if name else "low",
        timeout=MODEL_TIMEOUT_SECONDS,
        max_retries=0,
    )


def describe(error: Exception) -> str:
    """Describe an error in one short line."""
    first_line = str(error).partition("\n")[0].rstrip(".")
    return f"{type(error).__name__}: {first_line}"[:LONGEST_ERROR]


def money(amount: float) -> str:
    """Show an amount in US dollars, such as $1,250.00."""
    return f"${amount:,.2f}"


class FinishCheck(AgentMiddleware):
    """Send an agent back to work when it tries to finish with work undone."""

    def __init__(self, unfinished: Callable[[], str | None]) -> None:
        super().__init__()
        self.unfinished = unfinished
        self.reminders = 0

    @hook_config(can_jump_to=["model"])
    def after_model(
        self, state: AgentState[Any], runtime: Runtime[Any]
    ) -> dict[str, Any] | None:
        """When the model has finished, remind it of what's left, at most twice."""
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return None
        if self.reminders == MOST_REMINDERS:
            return None
        reminder = self.unfinished()
        if reminder is None:
            return None
        self.reminders += 1
        return {"messages": [HumanMessage(reminder)], "jump_to": "model"}


def harness(
    model_calls: int, unfinished: Callable[[], str | None]
) -> list[AgentMiddleware[Any, Any, Any]]:
    """Retry failed calls, stop an agent that runs too long, and check its work."""
    return [
        ModelRetryMiddleware(
            max_retries=RETRIES,
            on_failure="error",
            initial_delay=RETRY_DELAY_SECONDS,
        ),
        ToolRetryMiddleware(
            max_retries=RETRIES,
            retry_on=(httpx.TransportError,),
            on_failure="error",
            initial_delay=RETRY_DELAY_SECONDS,
        ),
        ModelCallLimitMiddleware(run_limit=model_calls, exit_behavior="error"),
        FinishCheck(unfinished),
    ]
