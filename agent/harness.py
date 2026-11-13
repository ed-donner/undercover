"""Agent construction and invocation, separate from claims business logic."""

from dataclasses import dataclass

from langchain.agents import AgentState, create_agent
from langchain.agents.middleware import AgentMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from agent.context import RunContext, RunState
from agent.model import model


@dataclass(frozen=True)
class AgentSpec:
    instructions: str
    tools: list[BaseTool]
    middleware: list[AgentMiddleware[AgentState, RunContext]]
    step_limit: int


def invoke(
    spec: AgentSpec,
    context: RunContext,
    thread_id: str,
    message: str,
    llm: BaseChatModel | None = None,
) -> str:
    agent = create_agent(
        llm or model(),
        tools=spec.tools,
        system_prompt=spec.instructions,
        context_schema=RunContext,
        state_schema=RunState,
        middleware=spec.middleware,
    )
    result = agent.invoke(
        {"messages": [{"role": "user", "content": message}]},
        context=context,
        config={
            "configurable": {"thread_id": thread_id},
            "recursion_limit": spec.step_limit,
        },
    )
    return result["messages"][-1].text
