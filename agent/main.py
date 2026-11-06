"""The Shoppie Agent."""

import os
from typing import Literal

import httpx
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, SecretStr

from agent.instructions import SYSTEM_PROMPT

load_dotenv(override=True)

BACKEND_URL = "http://localhost:8000"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-6-luna"
ProgressStage = Literal["reading_request", "checking_policy"]


class Recommendation(BaseModel):
    """Structured recommendation for a support agent to review."""

    outcome: Literal["approve", "decline", "request_information"]
    rationale: str
    policy_citations: list[str]
    next_action: str
    priority_human_review: bool


def backend() -> httpx.Client:
    """Return a client for the Shoppie backend."""
    return httpx.Client(base_url=BACKEND_URL, timeout=10)


def model() -> ChatOpenAI:
    """Return the model named in MODEL_NAME, or GPT-6 Luna by default."""
    name = os.getenv("MODEL_NAME")
    return ChatOpenAI(
        model=name or DEFAULT_MODEL,
        base_url=OPENROUTER_BASE_URL,
        api_key=SecretStr(os.environ["OPENROUTER_API_KEY"]),
        reasoning_effort=None if name else "low",
    )


def run(
    request_id: str, thread_id: str, llm: BaseChatModel | None = None
) -> dict[str, object]:
    """Run the agent on one support request and return its recommendation."""

    @tool
    def get_request_context() -> str:
        """Retrieve this request's safe customer, order, history, and policy context."""
        with backend() as client:
            response = client.get(f"/api/requests/{request_id}/context")
        response.raise_for_status()
        return response.text

    @tool
    def record_progress(stage: ProgressStage) -> str:
        """Record a supported progress stage for this request."""
        with backend() as client:
            response = client.post(
                f"/api/requests/{request_id}/steps", json={"stage": stage}
            )
        response.raise_for_status()
        return response.text

    agent = create_agent(
        llm or model(),
        tools=[get_request_context, record_progress],
        system_prompt=SYSTEM_PROMPT,
        response_format=ToolStrategy(Recommendation),
    )
    result = agent.invoke(
        {
            "messages": [
                {"role": "user", "content": "Review the assigned support request."}
            ]
        },
        config={"configurable": {"thread_id": thread_id}},
    )
    structured = result["structured_response"]
    return (
        structured.model_dump()
        if isinstance(structured, Recommendation)
        else structured
    )
