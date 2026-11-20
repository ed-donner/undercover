"""Claim workflow HTTP adapters."""

from fastapi import APIRouter, Request

from backend.agent_payment import AgentPaymentInput
from backend.dependencies import Database
from backend.documents import Documents, ReadInput, ReadRecord, SectionText
from backend.execution import execute
from backend.harness_models import AttemptInput, FinishInput
from backend.models import (
    ActivityEvent,
    ActivityInput,
    Claim,
    DecisionInput,
    PaymentInput,
    Run,
    SignOffInput,
    TextDocument,
)
from backend.workflow import Workflow

router = APIRouter()


@router.get("/claims/{claim_id}", operation_id="get_claim")
def get_claim(claim_id: str, db: Database) -> Claim:
    """Read a complete claim."""
    return Workflow(db).detail(claim_id)


@router.post("/claims/{claim_id}/runs", operation_id="start_claim", status_code=202)
def start_claim(
    claim_id: str, attempt: AttemptInput, db: Database, request: Request
) -> Run:
    """Start processing a waiting claim."""
    run = Workflow(db).start(claim_id, attempt.parent_run_id)
    if request.app.state.runner is not None:
        request.app.state.executor.submit(execute, db, run, request.app.state.runner)
    return run


@router.get("/claims/{claim_id}/runs", operation_id="list_runs")
def list_runs(claim_id: str, db: Database) -> list[Run]:
    """Read a claim's run history."""
    return Workflow(db).runs(claim_id)


@router.post("/claims/{claim_id}/decision", operation_id="record_decision")
def record_decision(claim_id: str, decision: DecisionInput, db: Database) -> Claim:
    """Record the agent's final decision."""
    return Workflow(db).decide(claim_id, decision)


@router.post("/claims/{claim_id}/sign-off", operation_id="sign_off_claim")
def sign_off_claim(claim_id: str, sign_off: SignOffInput, db: Database) -> Claim:
    """Record a handler's sign-off for an above-limit payout."""
    return Workflow(db).sign_off(claim_id, sign_off)


@router.post("/claims/{claim_id}/payment", operation_id="pay_claim")
def pay_claim(claim_id: str, payment: PaymentInput, db: Database) -> Claim:
    """Record a simulated payment of the approved amount."""
    return Workflow(db).request_payment(claim_id, payment)


@router.post("/claims/{claim_id}/agent-payment", operation_id="agent_pay_claim")
def agent_pay_claim(claim_id: str, payment: AgentPaymentInput, db: Database) -> Claim:
    """Request simulated payment with the active claim attempt's authority."""
    return Workflow(db).request_payment(claim_id, payment, payment.run_id)


@router.get("/claims/{claim_id}/events", operation_id="list_events")
def list_events(claim_id: str, db: Database) -> list[ActivityEvent]:
    """Read a claim's ordered public activity history."""
    return Workflow(db).events(claim_id)


@router.post("/runs/{run_id}/events", operation_id="record_activity")
def record_activity(run_id: str, activity: ActivityInput, db: Database) -> TextDocument:
    """Record an allowlisted agent activity without sensitive payloads."""
    Workflow(db).event(run_id, activity.activity)
    return TextDocument(text="Activity recorded")


@router.post("/claims/{claim_id}/reads", operation_id="read_claim_source")
def read_claim_source(claim_id: str, read: ReadInput, db: Database) -> SectionText:
    """Read and audit one source section for an active claim attempt."""
    return Documents(db).read(claim_id, read)


@router.get("/claims/{claim_id}/reads", operation_id="list_claim_source_reads")
def claim_source_reads(claim_id: str, db: Database) -> list[ReadRecord]:
    """Read the exact source sections delivered on this claim's attempts."""
    return Documents(db).reads(claim_id)


@router.post("/runs/{run_id}/finish", operation_id="finish_claim_attempt")
def finish_claim_attempt(
    run_id: str, finish: FinishInput, db: Database
) -> TextDocument:
    """Close and fence a child attempt after a delegation deadline or failure."""
    Workflow(db).close_attempt(run_id, finish.error)
    return TextDocument(text="Attempt finished")
