"""The Shoppie Agent's request agent: works one support request as a LangGraph graph."""

import json
import os
import time
from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from datetime import UTC, datetime
from typing import Annotated, Any, Literal, TypedDict

import httpx
import psycopg
from dotenv import load_dotenv
from langchain.agents.middleware import ModelRetryMiddleware, ToolRetryMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langfuse import propagate_attributes
from langfuse.langchain import CallbackHandler
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.types import Command, interrupt
from psycopg.rows import dict_row
from pydantic import SecretStr

from agent.instructions import REQUEST_INSTRUCTIONS
from agent.models import Recommendation
from agent.safety import apply_context_overrides, contains_unsupported_execution_claim
from backend.refunds import Line, RefundReason

load_dotenv(override=True)

BACKEND_URL = "http://localhost:8000"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "deepseek/deepseek-v4.1-flash"
SCHEMA = "undercover"
MAX_MODEL_CALLS = 30
MAX_RETRIES = 2
RETRY_DELAY = 1.0
ProgressStage = Literal["reading_request", "checking_policy"]
WorkStatus = Literal["done", "waiting", "left_for_support", "skipped"]

_CHECKPOINTER_CACHE: dict[str, BaseCheckpointSaver[Any]] = {}


class RequestState(TypedDict):
    """What the graph keeps for one support request."""

    messages: Annotated[list[Any], add_messages]
    request_id: str
    attempt: int
    recommendation: dict[str, Any] | None
    review: dict[str, Any] | None


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
            max_retries=MAX_RETRIES, initial_delay=RETRY_DELAY, on_failure="error"
        ),
        ToolRetryMiddleware(
            max_retries=MAX_RETRIES,
            initial_delay=RETRY_DELAY,
            retry_on=(httpx.TransportError,),
            on_failure="error",
        ),
    ]


def get_checkpointer() -> BaseCheckpointSaver[Any]:
    """Return a PostgresSaver when DATABASE_URL is set, or InMemorySaver otherwise."""
    database_url = os.getenv("DATABASE_URL")
    database_path = os.getenv("SHOPPIE_DATABASE_PATH")
    if database_url and not database_path:
        key = f"postgres:{database_url}"
        cached = _CHECKPOINTER_CACHE.get(key)
        if isinstance(cached, PostgresSaver) and not cached.conn.closed:
            return cached
        connect_kwargs: dict[str, Any] = {
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
            "options": f"-c search_path={SCHEMA}",
        }
        connection: Any = psycopg.connect(database_url, **connect_kwargs)
        connection.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
        saver = PostgresSaver(connection)
        saver.setup()
        _CHECKPOINTER_CACHE[key] = saver
        return saver
    key = f"memory:{database_path or 'default'}"
    if key not in _CHECKPOINTER_CACHE:
        _CHECKPOINTER_CACHE[key] = InMemorySaver()
    return _CHECKPOINTER_CACHE[key]


def call_with_retry(
    fn: Callable[..., Any],
    *args: Any,
    retry_on: tuple[type[Exception], ...] = (Exception,),
) -> Any:
    """Call a function, retrying transient errors up to MAX_RETRIES times."""
    for attempt in range(MAX_RETRIES + 1):
        try:
            return fn(*args)
        except retry_on:
            if attempt >= MAX_RETRIES:
                raise
            if RETRY_DELAY > 0:
                time.sleep(RETRY_DELAY)
    raise RuntimeError("Unreachable retry loop")


def refusal_message(response: httpx.Response) -> str:
    """Extract a readable backend refusal detail from a 4xx response."""
    try:
        detail = response.json().get("detail")
    except ValueError:
        detail = None
    return str(detail) if detail else response.text


def backend_get(path: str) -> httpx.Response:
    """Send a GET request to the backend with transport retry."""

    def _send() -> httpx.Response:
        with backend() as client:
            return client.get(path)

    return call_with_retry(_send, retry_on=(httpx.TransportError,))


def backend_post(path: str, payload: dict[str, Any] | None = None) -> httpx.Response:
    """Send a POST request to the backend with transport retry."""

    def _send() -> httpx.Response:
        with backend() as client:
            return client.post(path, json=payload)

    return call_with_retry(_send, retry_on=(httpx.TransportError,))


def make_request_tools(request_id: str) -> list[Any]:
    """Create the backend API tools for working one support request."""

    @tool
    def get_request_context() -> str:
        """Retrieve this request's customer message, evidence, order and history."""
        response = backend_get(f"/api/requests/{request_id}/context")
        response.raise_for_status()
        return response.text

    @tool
    def list_policy_sections() -> str:
        """List Shoppie's policies and the id and title of each section."""
        response = backend_get("/api/policies")
        response.raise_for_status()
        return response.text

    @tool
    def read_policy_section(policy: str, section: str) -> str:
        """Read one policy section by its policy and section id."""
        response = backend_get(
            f"/api/requests/{request_id}/policies/{policy}/sections/{section}"
        )
        if response.status_code == httpx.codes.NOT_FOUND:
            return "No such section. Use list_policy_sections for the ids."
        if (
            httpx.codes.BAD_REQUEST
            <= response.status_code
            < httpx.codes.INTERNAL_SERVER_ERROR
        ):
            return refusal_message(response)
        response.raise_for_status()
        return response.text

    @tool
    def calculate_refund(reason: RefundReason, lines: list[Line]) -> str:
        """Work out the eligible INR refund for covered items on this request."""
        response = backend_post(
            f"/api/requests/{request_id}/refund",
            {
                "reason": reason,
                "lines": [line.model_dump() for line in lines],
            },
        )
        if (
            httpx.codes.BAD_REQUEST
            <= response.status_code
            < httpx.codes.INTERNAL_SERVER_ERROR
        ):
            return refusal_message(response)
        response.raise_for_status()
        return response.text

    @tool
    def record_progress(stage: ProgressStage) -> str:
        """Record a supported progress stage for this request."""
        response = backend_post(f"/api/requests/{request_id}/steps", {"stage": stage})
        if (
            httpx.codes.BAD_REQUEST
            <= response.status_code
            < httpx.codes.INTERNAL_SERVER_ERROR
        ):
            return refusal_message(response)
        response.raise_for_status()
        return response.text

    return [
        get_request_context,
        list_policy_sections,
        read_policy_section,
        calculate_refund,
        record_progress,
    ]


def extract_request_context(messages: list[Any]) -> dict[str, Any] | None:
    """Return the parsed request context from the thread's ToolMessages, if read."""
    for message in reversed(messages):
        if isinstance(message, ToolMessage) and message.name == "get_request_context":
            return json.loads(str(message.content))
    return None


def after_agent(state: RequestState) -> Literal["tools", "decide"]:
    """Run the tools the model asked for, or move on to the decision."""
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return "decide"


def after_decide(state: RequestState) -> Literal["approval", "complete"]:
    """Pause for support agent sign-off unless a review is already present."""
    if state.get("review"):
        return "complete"
    return "approval"


def build_request_graph(
    request_id: str,
    llm: BaseChatModel | None = None,
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> Any:
    """Build and compile the synchronous StateGraph for one support request."""
    tools = make_request_tools(request_id)
    system_message = SystemMessage(REQUEST_INSTRUCTIONS)

    def agent(state: RequestState) -> dict[str, Any]:
        """Call the model with the conversation so far."""
        ai_calls = sum(1 for msg in state["messages"] if isinstance(msg, AIMessage))
        if ai_calls >= MAX_MODEL_CALLS:
            raise RuntimeError(
                f"Request {state['request_id']} exceeded {MAX_MODEL_CALLS} model calls"
            )
        model_with_tools = (llm or model()).bind_tools(tools)
        reply = call_with_retry(
            model_with_tools.invoke, [system_message, *state["messages"]]
        )
        return {"messages": [reply]}

    def decide(state: RequestState) -> dict[str, Any]:
        """Turn the agent's work into a structured recommendation and save it."""
        context = extract_request_context(state["messages"])
        if context is None:
            raise ValueError("The agent did not retrieve request context")
        decider = (llm or model()).with_structured_output(Recommendation)
        structured = call_with_retry(
            decider.invoke,
            [
                system_message,
                *state["messages"],
                HumanMessage("Record your recommendation on this support request."),
            ],
        )
        if not isinstance(structured, Recommendation):
            raise TypeError("The Shoppie Agent returned an invalid recommendation")
        if contains_unsupported_execution_claim(structured):
            raise ValueError("The recommendation claims an unconfirmed customer action")
        structured = apply_context_overrides(context, structured)
        recommendation = structured.model_dump()
        saved = backend_post(
            f"/api/requests/{state['request_id']}/recommendation", recommendation
        )
        saved.raise_for_status()
        return {"recommendation": recommendation}

    def approval(state: RequestState) -> dict[str, Any]:
        """Pause the graph until a support agent signs off on the recommendation."""
        answer = interrupt(
            {
                "request_id": state["request_id"],
                "recommendation": state["recommendation"],
            }
        )
        return {"review": answer}

    def complete(state: RequestState) -> dict[str, Any]:
        """Record the confirmed resolution and complete the request."""
        review = state.get("review") or {}
        payload = {
            "outcome": review["outcome"],
            "notes": review.get("notes", ""),
            "reviewed_by": review["reviewed_by"],
            "reviewed_at": review.get("reviewed_at") or datetime.now(UTC).isoformat(),
        }
        completed = backend_post(
            f"/api/requests/{state['request_id']}/complete", payload
        )
        completed.raise_for_status()
        return {"review": payload}

    builder = StateGraph(RequestState)
    builder.add_node("agent", agent)
    builder.add_node("tools", ToolNode(tools))
    builder.add_node("decide", decide)
    builder.add_node("approval", approval)
    builder.add_node("complete", complete)

    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", after_agent, ["tools", "decide"])
    builder.add_edge("tools", "agent")
    builder.add_conditional_edges("decide", after_decide, ["approval", "complete"])
    builder.add_edge("approval", "complete")
    builder.add_edge("complete", END)

    return builder.compile(checkpointer=checkpointer or get_checkpointer())


def run_request(
    request_id: str,
    thread_id: str,
    llm: BaseChatModel | None = None,
    attempt: int = 1,
) -> dict[str, Any]:
    """Run or resume the request graph until it pauses at approval."""
    graph = build_request_graph(request_id, llm)
    context_manager, config = trace_context(request_id, thread_id)
    state = graph.get_state(config)
    if state.values and state.next and state.next != ("approval",):
        with context_manager:
            result = graph.invoke(None, config, durability="sync")
        return result["recommendation"]
    if state.values and state.values.get("recommendation"):
        return state.values["recommendation"]
    initial_state: RequestState = {
        "messages": [HumanMessage("Review the assigned support request.")],
        "request_id": request_id,
        "attempt": attempt,
        "recommendation": None,
        "review": None,
    }
    with context_manager:
        result = graph.invoke(initial_state, config, durability="sync")
    return result["recommendation"]


def resume_request_thread(
    request_id: str,
    thread_id: str,
    review: dict[str, Any],
    llm: BaseChatModel | None = None,
) -> dict[str, Any]:
    """Resume a paused request thread with the support agent's sign-off."""
    graph = build_request_graph(request_id, llm)
    context_manager, config = trace_context(request_id, thread_id)
    state = graph.get_state(config)
    if state.next:
        with context_manager:
            return graph.invoke(Command(resume=review), config, durability="sync")
    payload = {
        "outcome": review["outcome"],
        "notes": review.get("notes", ""),
        "reviewed_by": review["reviewed_by"],
        "reviewed_at": review.get("reviewed_at") or datetime.now(UTC).isoformat(),
    }
    completed = backend_post(f"/api/requests/{request_id}/complete", payload)
    completed.raise_for_status()
    return {**(state.values or {}), "review": payload}


def resume_request(request_id: str, llm: BaseChatModel | None = None) -> dict[str, Any]:
    """Resume a signed-off request by its request id and complete it."""
    response = backend_get(f"/api/requests/{request_id}")
    if response.status_code == httpx.codes.NOT_FOUND:
        raise LookupError(f"Support request {request_id} not found")
    response.raise_for_status()
    detail = response.json()
    review = detail.get("review")
    if review is None:
        raise ValueError(f"Request {request_id} has no review to resume")
    if detail["status"] == "decided":
        return {"request_id": request_id, "status": "decided", "review": review}
    attempt = int(detail["attempts"]) + 1
    thread_id = f"request-{request_id}-attempt-{attempt}"
    result = resume_request_thread(request_id, thread_id, review, llm)
    return {
        "request_id": request_id,
        "status": "decided",
        "review": result.get("review") or review,
    }


def _skipped_result(request_id: str) -> WorkResult:
    return {
        "request_id": request_id,
        "status": "skipped",
        "line": f"{request_id}: not a waiting request, so not worked.",
    }


def work_request(request_id: str, llm: BaseChatModel | None = None) -> WorkResult:
    """Work one waiting or interrupted request and report back in a line."""
    response = backend_post(f"/api/requests/{request_id}/start")
    if response.status_code == httpx.codes.NOT_FOUND:
        return _skipped_result(request_id)
    if response.status_code == httpx.codes.CONFLICT:
        detail = backend_get(f"/api/requests/{request_id}").json()
        if detail["status"] != "in_progress":
            return _skipped_result(request_id)
        if detail.get("review") is not None:
            resumed = resume_request(request_id, llm)
            outcome = resumed["review"]["outcome"]
            return {
                "request_id": request_id,
                "status": "done",
                "line": f"{request_id}: {outcome}, completed after support review.",
            }
        attempt = int(detail["attempts"]) + 1
    else:
        response.raise_for_status()
        attempt = response.json()["attempt"]
    thread_id = f"request-{request_id}-attempt-{attempt}"
    try:
        recommendation = run_request(request_id, thread_id, llm, attempt=attempt)
    except Exception as error:
        get_checkpointer().delete_thread(thread_id)
        failure = backend_post(f"/api/requests/{request_id}/failure")
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
    return {
        "request_id": request_id,
        "status": "done",
        "line": f"{request_id}: {recommendation['outcome']}, "
        f"waiting for support review. {recommendation['next_action']}",
    }
