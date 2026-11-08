"""The agent's service: the web entry point the backend calls after a sign-off."""

from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import BackgroundTasks, Depends, FastAPI

from agent import agents, checkpoint


@asynccontextmanager
async def lifespan(_: FastAPI):
    checkpoint.saver()
    yield


app = FastAPI(title="UnderCover Agent", lifespan=lifespan)


def claim_worker() -> Callable[[str], str]:
    """Return what carries on with a claim; tests swap in a stub model."""
    return agents.decide_claim


@app.get("/api/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the agent's service is running."""
    return {"status": "ok"}


@app.post("/api/claims/{claim_id}/resume", operation_id="resume_claim", status_code=202)
def resume_claim(
    claim_id: str,
    background: BackgroundTasks,
    worker: Annotated[Callable[[str], str], Depends(claim_worker)],
) -> dict[str, str]:
    """Carry on with a signed-off claim, and pay it."""
    background.add_task(worker, claim_id)
    return {"claim_id": claim_id}
