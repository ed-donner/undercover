"""The UnderCover backend."""

import os
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from http import HTTPStatus
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request

from agent.main import run as run_agent
from backend.documents import (
    Documents,
    ReadInput,
    ReadRecord,
    SearchHit,
    SearchInput,
    SectionInfo,
    SectionText,
)
from backend.execution import Runner, execute
from backend.harness import Harness
from backend.harness_models import (
    AgentRun,
    AttemptInput,
    Completion,
    FinishInput,
    PlanInput,
    Start,
)
from backend.instructions import INSTRUCTIONS
from backend.models import (
    ActivityEvent,
    ActivityInput,
    Claim,
    Company,
    Customer,
    DecisionInput,
    Handler,
    PaymentInput,
    PlanDetails,
    Policy,
    QueueEntry,
    Run,
    SignOffInput,
    TextDocument,
    Wording,
)
from backend.store import Store
from backend.workflow import Workflow


def store(request: Request) -> Store:
    return request.app.state.store


Database = Annotated[Store, Depends(store)]


def create_app(
    database_path: Path | None = None, runner: Runner | None = run_agent
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        application.state.store.initialize()
        Workflow(application.state.store).recover()
        Harness(application.state.store).recover()
        application.state.executor = ThreadPoolExecutor(max_workers=4)
        yield
        application.state.executor.shutdown(wait=True)

    application = FastAPI(title="UnderCover", lifespan=lifespan)
    application.state.store = Store(
        database_path or Path(os.getenv("DATABASE_PATH", "undercover.db"))
    )
    application.state.runner = runner
    application.include_router(router)
    return application


router = APIRouter(prefix="/api")


@router.get("/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the backend is running."""
    return {"status": "ok"}


@router.get("/claims", operation_id="list_claims")
def list_claims(db: Database) -> list[QueueEntry]:
    """List the claims queue."""
    return [QueueEntry.model_validate(row) for row in db.queue()]


@router.get("/claims/{claim_id}", operation_id="get_claim")
def get_claim(claim_id: str, db: Database) -> Claim:
    """Read a complete claim."""
    return Workflow(db).detail(claim_id)


@router.get("/policies/{policy_id}", operation_id="get_policy")
def get_policy(policy_id: str, db: Database) -> Policy:
    """Read a customer's policy."""
    return Policy.model_validate(db.get("policies", policy_id))


@router.get("/customers/{customer_id}", operation_id="get_customer")
def get_customer(customer_id: str, db: Database) -> Customer:
    """Read a customer and their claim history."""
    return Customer.model_validate(db.get("customers", customer_id))


@router.get("/plans/{name}", operation_id="get_plan")
def get_plan(name: str, db: Database) -> PlanDetails:
    """Read a plan's benefits and available add-ons."""
    return PlanDetails.model_validate(db.plan(name))


@router.get("/handlers", operation_id="list_handlers")
def list_handlers(db: Database) -> list[Handler]:
    """List the claims handlers."""
    return [Handler.model_validate(row) for row in db.records("handlers")]


@router.get("/company", operation_id="get_company")
def get_company(db: Database) -> Company:
    """Read the pilot's company settings."""
    return Company.model_validate(db.get("company", "company"))


@router.get("/wording", operation_id="get_wording")
def get_wording(db: Database) -> Wording:
    """Read the policy wording and version."""
    return Wording.model_validate(db.get("wording", "wording"))


@router.get("/instructions", operation_id="get_instructions")
def get_instructions() -> TextDocument:
    """Read the agent's instructions."""
    return TextDocument(text=INSTRUCTIONS)


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
    workflow = Workflow(db)
    try:
        return workflow.pay(claim_id, payment)
    except HTTPException as exc:
        if exc.status_code == HTTPStatus.CONFLICT:
            workflow.payment_blocked(claim_id)
        raise


@router.get("/claims/{claim_id}/events", operation_id="list_events")
def list_events(claim_id: str, db: Database) -> list[ActivityEvent]:
    """Read a claim's ordered public activity history."""
    return Workflow(db).events(claim_id)


@router.post("/runs/{run_id}/events", operation_id="record_activity")
def record_activity(run_id: str, activity: ActivityInput, db: Database) -> TextDocument:
    """Record an allowlisted agent activity without sensitive payloads."""
    Workflow(db).event(run_id, activity.activity)
    return TextDocument(text="Activity recorded")


@router.post("/agent-runs", operation_id="start_agent_run", status_code=202)
def start_agent_run(start: Start, db: Database) -> AgentRun:
    """Start a queue or named-claim run with an explicit claim cap."""
    return Harness(db).create(start)


@router.get("/agent-runs", operation_id="list_agent_runs")
def list_agent_runs(db: Database) -> list[AgentRun]:
    """Read agent runs newest first, including the current run."""
    return Harness(db).history()


@router.get("/agent-runs/{run_id}", operation_id="get_agent_run")
def get_agent_run(run_id: str, db: Database) -> AgentRun:
    """Read an agent run and its persisted ordered to-do list."""
    return Harness(db).get(run_id)


@router.put("/agent-runs/{run_id}/tasks", operation_id="plan_agent_run")
def plan_agent_run(run_id: str, plan: PlanInput, db: Database) -> AgentRun:
    """Persist the agent's plan without changing recorded work outcomes."""
    return Harness(db).plan(run_id, plan.tasks)


@router.post("/agent-runs/{run_id}/check", operation_id="check_agent_run")
def check_agent_run(run_id: str, db: Database) -> Completion:
    """Reconcile claim outcomes and find missed work within the cap."""
    return Harness(db).check(run_id)


@router.post("/agent-runs/{run_id}/finish", operation_id="finish_agent_run")
def finish_agent_run(run_id: str, finish: FinishInput, db: Database) -> AgentRun:
    """Finalize a checked run or record a sanitized terminal failure."""
    return Harness(db).finish(run_id, finish.error)


@router.get("/documents", operation_id="list_document_sections")
def document_catalog(db: Database) -> list[SectionInfo]:
    """List section titles and versions of the two approved source documents."""
    return Documents(db).catalog()


@router.post("/documents/search", operation_id="search_document_sections")
def search_documents(search: SearchInput, db: Database) -> list[SearchHit]:
    """Find source sections by keyword without sending complete documents."""
    return Documents(db).search(search)


@router.get(
    "/documents/{document_id}/sections/{section}", operation_id="get_document_section"
)
def get_document_section(document_id: str, section: int, db: Database) -> SectionText:
    """Read a complete source section for a handler without claiming agent access."""
    return Documents(db).section(document_id, section)


@router.post("/claims/{claim_id}/reads", operation_id="read_claim_source")
def read_claim_source(claim_id: str, read: ReadInput, db: Database) -> SectionText:
    """Read and audit one source section for an active claim attempt."""
    return Documents(db).read(claim_id, read)


@router.get("/claims/{claim_id}/reads", operation_id="list_claim_source_reads")
def claim_source_reads(claim_id: str, db: Database) -> list[ReadRecord]:
    """Read the exact source sections delivered on this claim's attempts."""
    return Documents(db).reads(claim_id)


app = create_app()
