"""The UnderCover backend: the HTTP routes, each a thin call into the logic modules."""

from typing import Any, Literal

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend import agent_process, agent_service, claims, data, payouts, runs
from backend.errors import Conflict, NotFound
from backend.instructions import CLAIM_INSTRUCTIONS, QUEUE_INSTRUCTIONS
from backend.money import Amount
from backend.payouts import Benefit, Line

app = FastAPI(title="UnderCover")


@app.exception_handler(NotFound)
def not_found(_: Request, error: NotFound) -> JSONResponse:
    return JSONResponse({"detail": str(error)}, status_code=404)


@app.exception_handler(Conflict)
def conflict(_: Request, error: Conflict) -> JSONResponse:
    return JSONResponse({"detail": str(error)}, status_code=409)


class Decision(BaseModel):
    decision: Literal["approve", "decline", "refer"]
    payout: Amount
    reason: str
    policy_reference: str


class Step(BaseModel):
    text: str


class SignOff(BaseModel):
    handler_id: str


class Payment(BaseModel):
    amount: Amount


class PayoutRequest(BaseModel):
    policy_id: str
    benefit: Benefit
    lines: list[Line]
    paid_by_others: Amount


class StartRun(BaseModel):
    claim_ids: list[str]


class RunItemUpdate(BaseModel):
    status: Literal["to do", "in progress", "done", "left for a handler"]
    note: str


class FinishRun(BaseModel):
    summary: str


@app.get("/api/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the backend is running."""
    return {"status": "ok"}


@app.get("/api/claims", operation_id="list_claims")
def list_claims() -> list[dict[str, Any]]:
    """List every claim in the queue, oldest submitted first."""
    return claims.list_summaries()


@app.get("/api/claims/{claim_id}", operation_id="get_claim")
def get_claim(claim_id: str) -> dict[str, Any]:
    """Return one claim in full, with its policy and its customer's claim history."""
    return claims.get_full(claim_id)


@app.get("/api/documents/{document}/sections", operation_id="list_sections")
def list_sections(document: str) -> list[str]:
    """List a document's section headings, in order."""
    return list(data.get_document(document))


@app.get("/api/documents/{document}/section", operation_id="get_section")
def get_section(document: str, heading: str) -> dict[str, str]:
    """Return the text of one section of a document."""
    return {"text": data.get_section(document, heading)}


@app.get("/api/claim-instructions", operation_id="get_claim_instructions")
def get_claim_instructions() -> dict[str, str]:
    """Return the instructions for deciding one claim, read only."""
    return {"instructions": CLAIM_INSTRUCTIONS}


@app.get("/api/queue-instructions", operation_id="get_queue_instructions")
def get_queue_instructions() -> dict[str, str]:
    """Return the instructions for running the claims queue, read only."""
    return {"instructions": QUEUE_INSTRUCTIONS}


@app.post("/api/payouts", operation_id="calculate_payout")
def calculate_payout(request: PayoutRequest) -> dict[str, Any]:
    """Work out the payout on an approved claim with UnderCover's payout rules."""
    return payouts.work_out_payout(
        request.policy_id, request.benefit, request.lines, request.paid_by_others
    )


@app.get("/api/handlers", operation_id="list_handlers")
def list_handlers() -> list[dict[str, Any]]:
    """List the claims handlers who can sign off an over-limit payout."""
    return [h for h in data.HANDLERS if h["can_approve_over_limit"]]


@app.get("/api/unfinished-claims", operation_id="list_unfinished_claims")
def list_unfinished_claims() -> list[str]:
    """List the claims the agent must carry on with: stopped, or ready to pay."""
    return claims.list_unfinished()


@app.post("/api/claims/{claim_id}/decision", operation_id="decide_claim")
def decide_claim(claim_id: str, decision: Decision) -> dict[str, Any]:
    """Record a decision on a claim, approve, decline or refer."""
    return claims.decide(claim_id, **decision.model_dump())


@app.post("/api/claims/{claim_id}/steps", operation_id="record_step")
def record_step(claim_id: str, step: Step) -> dict[str, Any]:
    """Record one step of the agent's work on a claim."""
    claims.record_step(claim_id, step.text)
    return {"claim_id": claim_id, "text": step.text}


@app.get("/api/claims/{claim_id}/steps", operation_id="list_claim_steps")
def list_claim_steps(claim_id: str) -> list[dict[str, Any]]:
    """List a claim's steps, in the order they happened."""
    return claims.list_steps(claim_id)


@app.post("/api/claims/{claim_id}/sign-off", operation_id="sign_off_claim")
def sign_off_claim(
    claim_id: str, sign_off: SignOff, background: BackgroundTasks
) -> dict[str, Any]:
    """Have a handler sign off an over-limit approved claim's payout."""
    signed = claims.sign_off(claim_id, sign_off.handler_id)
    background.add_task(agent_service.notify_sign_off, claim_id)
    return signed


@app.post("/api/claims/{claim_id}/payment", operation_id="pay_claim")
def pay_claim(claim_id: str, payment: Payment) -> dict[str, Any]:
    """Pay a claim's approved payout, blocked until any required sign-off is given."""
    return claims.pay(claim_id, payment.amount)


@app.post("/api/claims/{claim_id}/run", operation_id="run_agent")
def run_agent(claim_id: str) -> dict[str, Any]:
    """Start the UnderCover Agent on a waiting claim."""
    claim = claims.start_work(claim_id)
    agent_process.start(claim_id)
    return claim


@app.post("/api/claims/{claim_id}/requeue", operation_id="requeue_claim")
def requeue_claim(claim_id: str) -> dict[str, Any]:
    """Put a stuck claim back in the queue as waiting."""
    return claims.requeue(claim_id)


@app.post("/api/runs", operation_id="start_run")
def start_run(start: StartRun) -> dict[str, Any]:
    """Start a run with one to-do item per claim."""
    return runs.start_run(start.claim_ids)


@app.get("/api/runs/current", operation_id="get_current_run")
def get_current_run() -> dict[str, Any] | None:
    """Return the most recently started run, with its items, or null."""
    return runs.get_current_run()


@app.post("/api/runs/{run_id}/items/{claim_id}", operation_id="update_run_item")
def update_run_item(
    run_id: int, claim_id: str, update: RunItemUpdate
) -> dict[str, Any]:
    """Update one run item's status and note."""
    return runs.update_run_item(run_id, claim_id, update.status, update.note)


@app.post("/api/runs/{run_id}/finish", operation_id="finish_run")
def finish_run(run_id: int, finish: FinishRun) -> dict[str, Any]:
    """Finish a run, recording its summary for the handlers."""
    return runs.finish_run(run_id, finish.summary)
