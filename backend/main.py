"""The Shoppie support backend."""

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request

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
