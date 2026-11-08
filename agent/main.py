"""The Shoppie Agent's request agent: works one support request from a clean start."""

import os
from contextlib import AbstractContextManager, nullcontext
from typing import Any, Literal, TypedDict

import httpx
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.middleware import ModelRetryMiddleware, ToolRetryMiddleware
from langchain.agents.structured_output import ToolStrategy
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langfuse import propagate_attributes
from langfuse.langchain import CallbackHandler
from pydantic import SecretStr

from agent.instructions import REQUEST_INSTRUCTIONS
from agent.models import Recommendation
from agent.safety import apply_context_overrides, contains_unsupported_execution_claim
from backend.refunds import Line, RefundReason

load_dotenv(override=True)

BACKEND_URL = "http://localhost:8000"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "deepseek/deepseek-v4.1-flash"
RETRY_DELAY = 1.0
ProgressStage = Literal["reading_request", "checking_policy"]
WorkStatus = Literal["done", "waiting", "left_for_support", "skipped"]


class WorkResult(TypedDict):
    """What happened when the request agent worked one request."""

    request_id: str
    status: WorkStatus
    line: str


def backend() -> httpx.Client:
    """Return a client for the Shoppie backend."""
    return httpx.Client(base_url=BACKEND_URL, timeout=30)


def model() -> ChatOpenAI:
    """Return the model named in MODEL_NAME, or DeepSeek V4.1 Flash by default."""
    name = os.getenv("MODEL_NAME")
    return ChatOpenAI(
        model=name or DEFAULT_MODEL,
        base_url=OPENROUTER_BASE_URL,
        api_key=SecretStr(os.environ["OPENROUTER_API_KEY"]),
        reasoning_effort=None if name else "low",
        timeout=120,
    )


def session_id_for(request_id: str, thread_id: str) -> str:
    """Name a request's Langfuse session after the request and its thread."""
    return thread_id if request_id in thread_id else f"{request_id}-{thread_id}"


def trace_context(
    request_id: str, thread_id: str
) -> tuple[AbstractContextManager[Any], RunnableConfig]:
    """Build the runnable config and Langfuse session context when keys are set."""
    session_id = session_id_for(request_id, thread_id)
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    if os.getenv("LANGFUSE_SECRET_KEY") and os.getenv("LANGFUSE_PUBLIC_KEY"):
        config["callbacks"] = [CallbackHandler()]
        config["metadata"] = {"langfuse_session_id": session_id}
        return propagate_attributes(session_id=session_id), config
    return nullcontext(), config


def retry_middleware() -> list[ModelRetryMiddleware | ToolRetryMiddleware]:
    """Retry model calls and backend calls that hit a passing error."""
    return [
        ModelRetryMiddleware(
            max_retries=2, initial_delay=RETRY_DELAY, on_failure="error"
        ),
        ToolRetryMiddleware(
            max_retries=2,
            initial_delay=RETRY_DELAY,
            retry_on=(httpx.TransportError,),
            on_failure="error",
        ),
    ]


def make_request_tools(
    request_id: str, request_context: dict[str, object]
) -> list[Any]:
    """Create the backend API tools for working one support request."""

    @tool
    def get_request_context() -> str:
        """Retrieve this request's customer message, evidence, order and history."""
        with backend() as client:
            response = client.get(f"/api/requests/{request_id}/context")
        response.raise_for_status()
        request_context.update(response.json())
        return response.text

    @tool
    def list_policy_sections() -> str:
        """List Shoppie's policies and the id and title of each section."""
        with backend() as client:
            response = client.get("/api/policies")
        response.raise_for_status()
        return response.text

    @tool
    def read_policy_section(policy: str, section: str) -> str:
        """Read one policy section by its policy and section id."""
        with backend() as client:
            response = client.get(
                f"/api/requests/{request_id}/policies/{policy}/sections/{section}"
            )
        if response.status_code == httpx.codes.NOT_FOUND:
            return "No such section. Use list_policy_sections for the ids."
        response.raise_for_status()
        return response.text

    @tool
    def calculate_refund(reason: RefundReason, lines: list[Line]) -> str:
        """Work out the eligible INR refund for covered items on this request."""
        with backend() as client:
            response = client.post(
                f"/api/requests/{request_id}/refund",
                json={
                    "reason": reason,
                    "lines": [line.model_dump() for line in lines],
                },
            )
        if response.status_code == httpx.codes.UNPROCESSABLE_ENTITY:
            return response.json().get("detail", "Invalid refund calculation input.")
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

    return [
        get_request_context,
        list_policy_sections,
        read_policy_section,
        calculate_refund,
        record_progress,
    ]


def run_request(
    request_id: str, thread_id: str, llm: BaseChatModel | None = None
) -> dict[str, object]:
    """Run the request agent on one request: approve, decline or request information."""
    request_context: dict[str, object] = {}
    agent = create_agent(
        llm or model(),
        tools=make_request_tools(request_id, request_context),
        system_prompt=REQUEST_INSTRUCTIONS,
        response_format=ToolStrategy(Recommendation),
        middleware=retry_middleware(),
    )
    context_manager, config = trace_context(request_id, thread_id)
    with context_manager:
        result = agent.invoke(
            {
                "messages": [
                    {"role": "user", "content": "Review the assigned support request."}
                ]
            },
            config=config,
        )
    structured = result["structured_response"]
    if not isinstance(structured, Recommendation):
        raise TypeError("The Shoppie Agent returned an invalid recommendation")
    if not request_context:
        raise ValueError("The agent did not retrieve request context")
    if contains_unsupported_execution_claim(structured):
        raise ValueError("The recommendation claims an unconfirmed customer action")
    structured = apply_context_overrides(request_context, structured)
    return structured.model_dump()


def work_request(request_id: str, llm: BaseChatModel | None = None) -> WorkResult:
    """Work one waiting request on a fresh thread and report back in a line."""
    with backend() as client:
        response = client.post(f"/api/requests/{request_id}/start")
    if response.status_code in {httpx.codes.NOT_FOUND, httpx.codes.CONFLICT}:
        return {
            "request_id": request_id,
            "status": "skipped",
            "line": f"{request_id}: not a waiting request, so not worked.",
        }
    response.raise_for_status()
    attempt = response.json()["attempt"]
    try:
        recommendation = run_request(
            request_id, f"request-{request_id}-attempt-{attempt}", llm
        )
    except Exception as error:
        with backend() as client:
            failure = client.post(f"/api/requests/{request_id}/failure")
        failure.raise_for_status()
        if failure.json()["status"] == "left_for_support":
            return {
                "request_id": request_id,
                "status": "left_for_support",
                "line": f"{request_id}: failed ({type(error).__name__}) on attempt "
                f"{attempt}, left for a support agent.",
            }
        return {
            "request_id": request_id,
            "status": "waiting",
            "line": f"{request_id}: failed ({type(error).__name__}) on attempt "
            f"{attempt}, back in the queue to be tried again.",
        }
    with backend() as client:
        saved = client.post(
            f"/api/requests/{request_id}/recommendation", json=recommendation
        )
    saved.raise_for_status()
    return {
        "request_id": request_id,
        "status": "done",
        "line": f"{request_id}: {recommendation['outcome']}, "
        f"waiting for support review. {recommendation['next_action']}",
    }
