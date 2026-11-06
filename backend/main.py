"""The Shoppie support backend."""

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request

from agent.instructions import SYSTEM_PROMPT
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
