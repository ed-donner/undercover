"""The Shoppie support backend."""

import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from pydantic import BaseModel

from agent.instructions import SYSTEM_PROMPT
from agent.main import run as run_agent
from backend.policies import policy_for_request_type
from backend.store import Store

DEFAULT_DATABASE_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "shoppie.sqlite3"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize SQLite and seed the Shoppie queue."""
    path = Path(os.getenv("SHOPPIE_DATABASE_PATH", DEFAULT_DATABASE_PATH))
    store = Store(path)
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
    notes: str = ""


def run_request_in_background(store: Store, request_id: str) -> None:
    """Run the Shoppie Agent and persist the result for agent review."""
    try:
        recommendation = run_agent(request_id, f"request-{request_id}")
        if not store.save_recommendation(request_id, recommendation):
            store.fail_run(request_id)
    except Exception:
        store.fail_run(request_id)


@app.get("/api/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the backend is running."""
    return {"status": "ok"}


@app.get("/api/requests", operation_id="list_requests")
def list_requests(request: Request) -> list[dict[str, Any]]:
    """List support requests in queue order."""
    return request.app.state.store.list_requests()


@app.get("/api/requests/{request_id}", operation_id="get_request")
def get_request(request_id: str, request: Request) -> dict[str, Any]:
    """Return a support request and its related records."""
    result = request.app.state.store.get_request(request_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Support request not found")
    return result


@app.get("/api/requests/{request_id}/context", operation_id="get_request_context")
def get_request_context(request_id: str, request: Request) -> dict[str, Any]:
    """Return the request context and policy available to the agent."""
    result = request.app.state.store.get_request(request_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Support request not found")
    try:
        result["policy"] = policy_for_request_type(result["request"]["type"])
    except KeyError as error:
        raise HTTPException(
            status_code=422, detail="Unsupported request type"
        ) from error
    return result


@app.get("/api/agent/instructions", operation_id="get_agent_instructions")
def get_agent_instructions() -> dict[str, str]:
    """Return the current read-only Shoppie Agent instructions."""
    return {"instructions": SYSTEM_PROMPT}


@app.post("/api/requests/{request_id}/steps", operation_id="add_request_step")
def add_request_step(
    request_id: str, progress: ProgressInput, request: Request
) -> dict[str, str]:
    """Record a supported agent progress step."""
    allowed = {"reading_request", "checking_policy"}
    if progress.stage not in allowed:
        raise HTTPException(status_code=422, detail="Unsupported progress stage")
    if not request.app.state.store.add_step(request_id, progress.stage):
        raise HTTPException(status_code=409, detail="Request is not in progress")
    return {"status": "recorded", "stage": progress.stage}


@app.post("/api/requests/{request_id}/run", operation_id="run_request")
def run_request(
    request_id: str, request: Request, background_tasks: BackgroundTasks
) -> dict[str, str]:
    """Start agent work for a support request."""
    store: Store = request.app.state.store
    if store.get_request(request_id) is None:
        raise HTTPException(status_code=404, detail="Support request not found")
    if not store.start_run(request_id):
        raise HTTPException(status_code=409, detail="Request cannot be run")
    background_tasks.add_task(run_request_in_background, store, request_id)
    return {"request_id": request_id, "status": "in_progress"}


@app.post("/api/requests/{request_id}/review", operation_id="review_request")
def review_request(
    request_id: str, review: ReviewInput, request: Request
) -> dict[str, Any]:
    """Record a support decision without processing the order."""
    result = request.app.state.store.get_request(request_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Support request not found")
    if result["status"] != "waiting_for_agent_review":
        raise HTTPException(status_code=409, detail="Request is not ready for review")
    saved_review = {
        "outcome": review.outcome,
        "notes": review.notes,
        "reviewed_at": datetime.now(UTC).isoformat(),
    }
    if not request.app.state.store.record_review(request_id, saved_review):
        raise HTTPException(status_code=409, detail="Request was already reviewed")
    return {"request_id": request_id, "status": "decided", "review": saved_review}
