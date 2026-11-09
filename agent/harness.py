"""The agent harness: the model, and one way to run an agent to its final reply.

Nothing here knows about claims. What an agent can do is in `tools.py`.
"""

import os
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

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


@dataclass
class AgentSpec:
    """What an agent is: its instructions and its tools."""

    instructions: str
    tools: Sequence[BaseTool]


def run_agent(
    spec: AgentSpec,
    context: Any,
    task: str,
    llm: BaseChatModel | None = None,
    config: RunnableConfig | None = None,
) -> str:
    """Run an agent on a task until it stops calling tools, and return its reply.

    `context` is handed to every tool through its `ToolRuntime`; `config` carries
    the run's callbacks and metadata.
    """
    agent = create_agent(
        llm or model(),
        tools=spec.tools,
        system_prompt=spec.instructions,
        context_schema=type(context),
    )
    result = agent.invoke(
        {"messages": [{"role": "user", "content": task}]},
        config=config,
        context=context,
    )
    return result["messages"][-1].text
