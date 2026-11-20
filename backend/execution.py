"""Background execution boundary for one claim run."""

import logging
from collections.abc import Callable

from backend.harness import Harness
from backend.harness_models import AgentRun
from backend.models import Run
from backend.store import Store
from backend.workflow import Workflow

Runner = Callable[[str, str], str]
logger = logging.getLogger(__name__)


def execute(store: Store, run: Run, runner: Runner) -> None:
    error = None
    try:
        runner(run.claim_id, run.thread_id)
    except Exception as exc:
        logger.warning("Claim run failed (%s)", type(exc).__name__)
        error = "Agent could not finish. Check connectivity and model configuration."
    Workflow(store).finish(run.run_id, error)


def execute_queue(store: Store, run: AgentRun, runner: Runner) -> None:
    for attempt in range(2):
        try:
            runner(
                run.run_id, run.thread_id if not attempt else f"{run.thread_id}:retry"
            )
            if Harness(store).get(run.run_id).status == "completed":
                return
        except Exception as exc:
            logger.warning("Queue invocation failed (%s)", type(exc).__name__)
        if Harness(store).get(run.run_id).status != "running":
            return
        workflow = Workflow(store)
        for claim_id in run.scope:
            for child in workflow.runs(claim_id):
                if child.parent_run_id == run.run_id and child.status == "running":
                    workflow.finish(child.run_id, "Queue invocation interrupted.")
    Harness(store).finish(run.run_id, "Agent could not finish.")
