"""The Shoppie Agent web service for resuming signed-off requests and starting runs."""

from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from agent import main

app = FastAPI(title="Shoppie Agent")


class AgentRunInput(BaseModel):
    """The most requests a queue run may work."""

    cap: int = Field(ge=1)


@app.get("/health", operation_id="agent_health")
def health() -> dict[str, str]:
    """Check that the Shoppie Agent service is running."""
    return {"status": "ok"}


@app.post("/requests/{request_id}/resume", operation_id="resume_request")
def resume_request(request_id: str) -> dict[str, Any]:
    """Resume a paused support request thread after support sign-off."""
    try:
        return main.resume_request(request_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/runs", operation_id="start_agent_run")
def start_agent_run(run: AgentRunInput) -> dict[str, Any]:
    """Start a capped queue run through the Shoppie backend."""
    with main.backend() as client:
        response = client.post("/api/runs", json={"cap": run.cap})
    if response.status_code == httpx.codes.CONFLICT:
        raise HTTPException(status_code=409, detail="A run is already in progress")
    response.raise_for_status()
    return response.json()
