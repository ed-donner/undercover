"""Queue-run HTTP adapters."""

from fastapi import APIRouter, Request

from backend.dependencies import Database
from backend.execution import execute_queue
from backend.harness import Harness
from backend.harness_models import AgentRun, Completion, FinishInput, PlanInput, Start

router = APIRouter()


@router.post("/agent-runs", operation_id="start_agent_run", status_code=202)
def start_agent_run(start: Start, db: Database, request: Request) -> AgentRun:
    """Start a queue or named-claim run with an explicit claim cap."""
    run = Harness(db).create(start)
    if request.app.state.queue_runner is not None:
        request.app.state.executor.submit(
            execute_queue, db, run, request.app.state.queue_runner
        )
    return run


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
