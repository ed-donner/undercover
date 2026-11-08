"""The Shoppie support backend."""

import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import httpx
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from agent.instructions import QUEUE_INSTRUCTIONS, REQUEST_INSTRUCTIONS
from agent.models import Recommendation
from agent.queue import run_queue
from backend.policies import list_policies, read_section
from backend.refunds import RefundCalculation, RefundInput, work_out_refund
from backend.store import AGENT_STAGES, Store, TodoStatus

DEFAULT_DATABASE_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "shoppie.sqlite3"
)
DEFAULT_AGENT_URL = "http://127.0.0.1:8002"


def database_path() -> Path:
    """Return the SQLite path from SHOPPIE_DATABASE_PATH or the default."""
    return Path(os.getenv("SHOPPIE_DATABASE_PATH", DEFAULT_DATABASE_PATH))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the database and seed the Shoppie queue."""
    store = Store()
    store.initialize()
    app.state.store = store
    yield


app = FastAPI(title="Shoppie", lifespan=lifespan)


class ProgressInput(BaseModel):
    """A supported progress stage supplied by the agent."""

    stage: str


class ReviewInput(BaseModel):
    """A support agent's reviewed recommendation."""

    outcome: Literal["approve", "decline", "request_information"]
    notes: str
    reviewed_by: str = Field(min_length=1)


class CompletionInput(BaseModel):
    """A confirmed review used by the agent to complete a request."""

    outcome: Literal["approve", "decline", "request_information"]
    notes: str
    reviewed_by: str
    reviewed_at: str


class RunInput(BaseModel):
    """The most requests a run may work."""

    cap: int = Field(ge=1)


class TodoItem(BaseModel):
    """One item on a run's to-do list."""

    request_id: str
    title: str
    status: TodoStatus


class TodoList(BaseModel):
    """A run's whole to-do list."""

    todos: list[TodoItem]


class TodoStatusInput(BaseModel):
    """A new status for one to-do item."""

    status: TodoStatus


def store_of(request: Request) -> Store:
    """Return the app's store."""
    return request.app.state.store


def require_request(store: Store, request_id: str) -> dict[str, Any]:
    """Return a request or raise 404."""
    result = store.get_request(request_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Support request not found")
    return result


def run_in_background(store: Store, run_id: str, cap: int) -> None:
    """Run the queue agent and store its summary, or mark the run failed."""
    try:
        summary = run_queue(run_id, cap)
    except Exception as error:
        store.finish_run(run_id, "failed", f"The run stopped: {error}")
        return
    store.finish_run(run_id, "finished", summary)


def agent_service_url() -> str:
    """Return the base URL of the Shoppie Agent service."""
    return os.getenv("UNDERCOVER_AGENT", DEFAULT_AGENT_URL).rstrip("/")


def notify_agent_resume(request_id: str) -> None:
    """Tell the agent service to resume a signed-off request when reachable."""
    try:
        httpx.post(f"{agent_service_url()}/requests/{request_id}/resume", timeout=30)
    except Exception:
        return


@app.get("/api/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the backend is running."""
    return {"status": "ok"}


@app.get("/api/requests", operation_id="list_requests")
def list_requests(request: Request) -> list[dict[str, Any]]:
    """List support requests in queue order."""
    return store_of(request).list_requests()


@app.get("/api/requests/waiting", operation_id="list_waiting_requests")
def list_waiting_requests(request: Request) -> list[dict[str, str]]:
    """List the id, type and creation time of each waiting request."""
    return store_of(request).list_waiting()


@app.get("/api/requests/{request_id}", operation_id="get_request")
def get_request(request_id: str, request: Request) -> dict[str, Any]:
    """Return a support request and its related records."""
    return require_request(store_of(request), request_id)


@app.get("/api/requests/{request_id}/context", operation_id="get_request_context")
def get_request_context(request_id: str, request: Request) -> dict[str, Any]:
    """Return the request, customer and order context available to the agent."""
    return require_request(store_of(request), request_id)


@app.get("/api/policies", operation_id="list_policy_sections")
def list_policy_sections() -> list[dict[str, object]]:
    """List Shoppie's policies and the sections in each."""
    return list_policies()


@app.get(
    "/api/requests/{request_id}/policies/{policy}/sections/{section}",
    operation_id="read_policy_section",
)
def read_policy_section(
    request_id: str, policy: str, section: str, request: Request
) -> dict[str, str]:
    """Return one policy section and record on the request that the agent read it."""
    store = store_of(request)
    require_request(store, request_id)
    result = read_section(policy, section)
    if result is None:
        raise HTTPException(status_code=404, detail="Policy section not found")
    message = f"Read {result['name']}, {result['title']}."
    if not store.add_step(request_id, "read_section", message):
        raise HTTPException(status_code=409, detail="Request is not in progress")
    return result


@app.get("/api/agent/instructions", operation_id="get_agent_instructions")
def get_agent_instructions() -> dict[str, str]:
    """Return the read-only instructions for running the queue and working a request."""
    return {"queue": QUEUE_INSTRUCTIONS, "request": REQUEST_INSTRUCTIONS}


@app.post("/api/requests/{request_id}/steps", operation_id="add_request_step")
def add_request_step(
    request_id: str, progress: ProgressInput, request: Request
) -> dict[str, str]:
    """Record a supported agent progress step."""
    if progress.stage not in AGENT_STAGES:
        raise HTTPException(status_code=422, detail="Unsupported progress stage")
    if not store_of(request).add_step(request_id, progress.stage):
        raise HTTPException(status_code=409, detail="Request is not in progress")
    return {"status": "recorded", "stage": progress.stage}


@app.post("/api/requests/{request_id}/refund", operation_id="calculate_refund")
def calculate_refund(
    request_id: str, refund: RefundInput, request: Request
) -> RefundCalculation:
    """Calculate the policy-backed refund for a request in progress."""
    store = store_of(request)
    record = require_request(store, request_id)
    if not store.is_in_progress(request_id):
        raise HTTPException(status_code=409, detail="Request is not in progress")
    try:
        result = work_out_refund(record["order"], refund.reason, refund.lines)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    store.add_step(
        request_id,
        "calculated_refund",
        f"Calculated eligible refund of ₹{result['refund']:,.2f}.",
    )
    return result


@app.post("/api/requests/{request_id}/start", operation_id="start_request")
def start_request(request_id: str, request: Request) -> dict[str, Any]:
    """Move a waiting request into progress for the agent."""
    store = store_of(request)
    require_request(store, request_id)
    attempt = store.start_request(request_id)
    if attempt is None:
        raise HTTPException(status_code=409, detail="Request is not waiting")
    return {"request_id": request_id, "status": "in_progress", "attempt": attempt}


@app.post(
    "/api/requests/{request_id}/recommendation", operation_id="save_recommendation"
)
def save_recommendation(
    request_id: str, recommendation: Recommendation, request: Request
) -> dict[str, str]:
    """Store the agent's one recommendation for support review."""
    store = store_of(request)
    require_request(store, request_id)
    if not store.save_recommendation(request_id, recommendation.model_dump()):
        raise HTTPException(status_code=409, detail="Request cannot take a decision")
    return {"request_id": request_id, "status": "waiting_for_agent_review"}


@app.post("/api/requests/{request_id}/failure", operation_id="record_failure")
def record_failure(request_id: str, request: Request) -> dict[str, str]:
    """Count a failed attempt and return the request to the queue or to support."""
    store = store_of(request)
    require_request(store, request_id)
    result = store.fail_request(request_id)
    if result is None:
        raise HTTPException(status_code=409, detail="Request is not in progress")
    return {"request_id": request_id, "status": result}


@app.post("/api/requests/{request_id}/review", operation_id="review_request")
def review_request(
    request_id: str,
    review: ReviewInput,
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """Record a support decision and trigger agent completion without order actions."""
    store = store_of(request)
    result = require_request(store, request_id)
    if result["status"] not in {"waiting_for_agent_review", "in_progress", "decided"}:
        raise HTTPException(status_code=409, detail="Request is not ready for review")
    saved_review = {
        "outcome": review.outcome,
        "notes": review.notes,
        "reviewed_by": review.reviewed_by,
        "reviewed_at": (result.get("review") or {}).get("reviewed_at")
        or datetime.now(UTC).isoformat(),
    }
    status = store.record_review(request_id, saved_review)
    if status is None:
        raise HTTPException(status_code=409, detail="Request was already reviewed")
    if status == "in_progress":
        background_tasks.add_task(notify_agent_resume, request_id)
    return {"request_id": request_id, "status": status, "review": saved_review}


@app.post("/api/requests/{request_id}/complete", operation_id="complete_request")
def complete_request(
    request_id: str, completion: CompletionInput, request: Request
) -> dict[str, Any]:
    """Record the confirmed resolution and complete a reviewed support request."""
    store = store_of(request)
    require_request(store, request_id)
    payload = completion.model_dump()
    if not store.complete_request(request_id, payload):
        raise HTTPException(status_code=409, detail="Request cannot be completed")
    return {"request_id": request_id, "status": "decided", "review": payload}


@app.post("/api/runs", operation_id="start_run")
def start_run(
    run: RunInput, request: Request, background_tasks: BackgroundTasks
) -> dict[str, Any]:
    """Start one agent run over the waiting requests, up to its cap."""
    store = store_of(request)
    run_id = store.create_run(run.cap)
    if run_id is None:
        raise HTTPException(status_code=409, detail="A run is already in progress")
    background_tasks.add_task(run_in_background, store, run_id, run.cap)
    return {"run_id": run_id, "cap": run.cap, "status": "running"}


@app.get("/api/runs/current", operation_id="get_current_run")
def get_current_run(request: Request) -> dict[str, Any] | None:
    """Return the latest run with its to-do list."""
    return store_of(request).current_run()


@app.put("/api/runs/{run_id}/todos", operation_id="write_run_todos")
def write_run_todos(run_id: str, todos: TodoList, request: Request) -> dict[str, str]:
    """Replace a running run's to-do list."""
    store = store_of(request)
    if not store.is_running(run_id):
        raise HTTPException(status_code=409, detail="Run is not running")
    store.write_todos(run_id, [todo.model_dump() for todo in todos.todos])
    return {"run_id": run_id, "status": "recorded"}


@app.post("/api/runs/{run_id}/todos/{request_id}", operation_id="update_run_todo")
def update_run_todo(
    run_id: str, request_id: str, update: TodoStatusInput, request: Request
) -> dict[str, str]:
    """Set the status of one item on a running run's to-do list."""
    store = store_of(request)
    if not store.is_running(run_id):
        raise HTTPException(status_code=409, detail="Run is not running")
    store.update_todo(run_id, request_id, update.status)
    return {"run_id": run_id, "request_id": request_id, "status": update.status}
