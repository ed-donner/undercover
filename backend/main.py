"""The UnderCover backend."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from backend import claims, decisions, runner
from backend.db import session
from backend.models import (
    ClaimContext,
    ClaimDetail,
    ClaimSummary,
    DecisionIn,
    DecisionRecord,
    Handler,
    Instructions,
    Payment,
    PaymentIn,
    PolicyWording,
    RunStatus,
    SignOffIn,
    Step,
    StepIn,
)
from backend.seed import init_db


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(title="UnderCover", lifespan=lifespan)

INSTRUCTIONS = Path(__file__).parent / "instructions.md"


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


@app.post("/api/claims/{claim_id}/decision", operation_id="record_decision")
def record_decision(claim_id: str, body: DecisionIn) -> DecisionRecord:
    """Record the decision, payout, explanation and policy section for a claim."""
    with session() as conn:
        return decisions.record_decision(conn, claim_id, body)


@app.post("/api/claims/{claim_id}/payment", operation_id="pay_claim")
def pay_claim(claim_id: str, body: PaymentIn) -> Payment:
    """Pay an approved claim the amount; refused over the limit until signed off."""
    with session() as conn:
        return decisions.pay(conn, claim_id, body)


@app.post("/api/claims/{claim_id}/sign-off", operation_id="sign_off_claim")
def sign_off_claim(claim_id: str, body: SignOffIn) -> Payment:
    """Let a handler sign off an approved payout over the limit, which pays it."""
    with session() as conn:
        return decisions.sign_off(conn, claim_id, body)


@app.post("/api/claims/{claim_id}/steps", operation_id="record_step")
def record_step(claim_id: str, body: StepIn) -> Step:
    """Record one step of the agent's work on a claim."""
    with session() as conn:
        return decisions.record_step(conn, claim_id, body)


@app.get("/api/claims/{claim_id}/steps", operation_id="list_steps")
def list_steps(claim_id: str) -> list[Step]:
    """List the steps of the agent's work on a claim, oldest first."""
    with session() as conn:
        return decisions.list_steps(conn, claim_id)


@app.get("/api/instructions", operation_id="get_instructions")
def get_instructions() -> Instructions:
    """Get the agent's instructions."""
    return Instructions(text=INSTRUCTIONS.read_text(encoding="utf-8"))


@app.post("/api/claims/{claim_id}/run", operation_id="start_claim_run", status_code=202)
def start_claim_run(claim_id: str) -> RunStatus:
    """Start the agent on one claim that has no decision yet."""
    return runner.start_claim_run(claim_id)


@app.post("/api/runs", operation_id="start_queue_run", status_code=202)
def start_queue_run() -> RunStatus:
    """Start the agent on every waiting claim, one after another."""
    return runner.start_queue_run()


@app.get("/api/runs/current", operation_id="get_run_status")
def get_run_status() -> RunStatus:
    """Say whether the agent is running, and on which claim."""
    return runner.RUNNER.status()
