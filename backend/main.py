"""The UnderCover backend."""

import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException

from backend import claims, runner, workflow
from backend.db import DATA, get_db, init_db
from backend.models import (
    ClaimDetail,
    ClaimSummary,
    Customer,
    DecisionRequest,
    Handler,
    Payment,
    PaymentRequest,
    Policy,
    QueueRun,
    SignOffRequest,
    Step,
    StepRequest,
    Text,
)

INSTRUCTIONS = Path(__file__).parent / "instructions.md"

Db = Annotated[sqlite3.Connection, Depends(get_db)]


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(title="UnderCover", lifespan=lifespan)


def found[T](item: T | None, name: str) -> T:
    if item is None:
        raise HTTPException(404, f"{name} not found")
    return item


@app.get("/api/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the backend is running."""
    return {"status": "ok"}


@app.get("/api/claims", operation_id="list_claims")
def list_claims(db: Db) -> list[ClaimSummary]:
    """List every claim in the queue with its status."""
    return claims.summaries(db)


@app.get("/api/claims/{claim_id}", operation_id="get_claim")
def get_claim(claim_id: str, db: Db) -> ClaimDetail:
    """Get one claim in full, with its decision, payment and sign-off."""
    return found(claims.claim_detail(db, claim_id), "Claim")


@app.get("/api/policies/{policy_id}", operation_id="get_policy")
def get_policy(policy_id: str, db: Db) -> Policy:
    """Get a policy with its plan, add-ons, trip and travelers."""
    return found(claims.policy(db, policy_id), "Policy")


@app.get("/api/customers/{customer_id}", operation_id="get_customer")
def get_customer(customer_id: str, db: Db) -> Customer:
    """Get a customer's name and claim history."""
    return found(claims.customer(db, customer_id), "Customer")


@app.get("/api/policy-wording", operation_id="get_policy_wording")
def get_policy_wording() -> Text:
    """Get the policy wording that decisions follow."""
    return Text(text=(DATA / "policy_wording.md").read_text(encoding="utf-8"))


@app.get("/api/instructions", operation_id="get_instructions")
def get_instructions() -> Text:
    """Get the UnderCover Agent's instructions."""
    return Text(text=INSTRUCTIONS.read_text(encoding="utf-8"))


@app.get("/api/handlers", operation_id="list_handlers")
def list_handlers(db: Db) -> list[Handler]:
    """List the claims handlers."""
    return claims.handlers(db)


@app.get("/api/claims/{claim_id}/steps", operation_id="list_steps")
def list_steps(claim_id: str, db: Db) -> list[Step]:
    """List what the agent did on a claim, step by step."""
    return workflow.steps(db, claim_id)


@app.post("/api/claims/{claim_id}/start", operation_id="start_claim")
def start_claim(claim_id: str, db: Db) -> ClaimDetail:
    """Mark a claim as in progress because the agent has started on it."""
    workflow.start(db, claim_id)
    return get_claim(claim_id, db)


@app.post("/api/claims/{claim_id}/decision", operation_id="record_decision")
def record_decision(claim_id: str, request: DecisionRequest, db: Db) -> ClaimDetail:
    """Record the decision, payout and reasons for a claim in progress."""
    workflow.decide(db, claim_id, request)
    return get_claim(claim_id, db)


@app.post("/api/claims/{claim_id}/payment", operation_id="pay_claim")
def pay_claim(claim_id: str, request: PaymentRequest, db: Db) -> Payment:
    """Pay an approved claim the given amount, once any sign-off it needs is in."""
    return workflow.pay(db, claim_id, request.amount)


@app.post("/api/claims/{claim_id}/sign-off", operation_id="sign_off_claim")
def sign_off_claim(claim_id: str, request: SignOffRequest, db: Db) -> ClaimDetail:
    """Sign off a payout over the limit as a handler, which releases the payment."""
    workflow.sign_off(db, claim_id, request.handler_id)
    return get_claim(claim_id, db)


@app.post("/api/claims/{claim_id}/steps", operation_id="add_step")
def add_step(claim_id: str, request: StepRequest, db: Db) -> Step:
    """Record one step the agent took on a claim."""
    return workflow.add_step(db, claim_id, request)


@app.post("/api/claims/{claim_id}/run", operation_id="run_claim", status_code=202)
def run_claim(claim_id: str, background: BackgroundTasks, db: Db) -> ClaimDetail:
    """Start the agent on a waiting claim."""
    if workflow.status_of(db, claim_id) != "waiting":
        raise HTTPException(409, "The claim is not waiting")
    workflow.start(db, claim_id)
    background.add_task(runner.run_claim, claim_id)
    return get_claim(claim_id, db)


@app.post("/api/queue/run", operation_id="run_queue", status_code=202)
def run_queue(background: BackgroundTasks, db: Db) -> QueueRun:
    """Start the agent on every waiting claim, one after another."""
    waiting = sum(1 for claim in claims.summaries(db) if claim.status == "waiting")
    background.add_task(runner.run_waiting)
    return QueueRun(waiting=waiting)
