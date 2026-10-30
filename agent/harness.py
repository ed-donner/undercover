"""The agent harness: the model, and one way to run an agent to its final reply.

Nothing here knows about claims. What an agent can do is in `tools.py`.
"""

import os
from collections.abc import Sequence
from typing import Any

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

load_dotenv(override=True)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "deepseek/deepseek-v4.1-flash"
MODEL_TIMEOUT_SECONDS = 120


def model() -> ChatOpenAI:
    """Return the model named in MODEL_NAME, or DeepSeek V4.1 Flash by default."""
    name = os.getenv("MODEL_NAME")
    return ChatOpenAI(
        model=name or DEFAULT_MODEL,
        base_url=OPENROUTER_BASE_URL,
        api_key=SecretStr(os.environ["OPENROUTER_API_KEY"]),
        reasoning_effort=None if name else "low",
        timeout=MODEL_TIMEOUT_SECONDS,
    )


def run_agent(
    instructions: str,
    tools: Sequence[BaseTool],
    context: Any,
    task: str,
    llm: BaseChatModel | None = None,
) -> str:
    """Run an agent on a task until it stops calling tools, and return its reply.

    `context` is handed to every tool through its `ToolRuntime`.
    """
    agent = create_agent(
        llm or model(),
        tools=tools,
        system_prompt=instructions,
        context_schema=type(context),
    )
    result = agent.invoke(
        {"messages": [{"role": "user", "content": task}]}, context=context
    )
    return result["messages"][-1].text
