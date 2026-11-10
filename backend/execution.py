"""Background execution boundary for one claim run."""

import logging
from collections.abc import Callable

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
