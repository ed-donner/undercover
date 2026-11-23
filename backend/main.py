"""The UnderCover backend."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend import claims
from backend.db import session
from backend.models import (
    ClaimContext,
    ClaimDetail,
    ClaimSummary,
    Handler,
    PolicyWording,
)
from backend.seed import init_db


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(title="UnderCover", lifespan=lifespan)


@app.get("/api/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the backend is running."""
    return {"status": "ok"}


@app.get("/api/claims", operation_id="list_claims")
def list_claims() -> list[ClaimSummary]:
    """List every claim in the queue with where it stands."""
    with session() as conn:
        return claims.list_summaries(conn)


@app.get("/api/claims/{claim_id}", operation_id="get_claim")
def get_claim(claim_id: str) -> ClaimDetail:
    """Get one claim in full, with its policy, plan, customer and state."""
    with session() as conn:
        return claims.get_detail(conn, claim_id)


@app.get("/api/claims/{claim_id}/context", operation_id="get_claim_context")
def get_claim_context(claim_id: str) -> ClaimContext:
    """Get what is needed to decide a claim: the claim, policy, plan and history."""
    with session() as conn:
        return claims.get_context(conn, claim_id)


@app.get("/api/policy-wording", operation_id="get_policy_wording")
def get_policy_wording() -> PolicyWording:
    """Get the text of the policy wording."""
    with session() as conn:
        return PolicyWording(text=claims.policy_wording(conn))


@app.get("/api/handlers", operation_id="list_handlers")
def list_handlers() -> list[Handler]:
    """List the claims handlers."""
    with session() as conn:
        return claims.list_handlers(conn)
