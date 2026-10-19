"""Running the agent in the background."""

import logging
import uuid

from agent.claim_agent import work
from agent.queue_agent import queue_run

log = logging.getLogger(__name__)


def run_claim(claim_id: str) -> None:
    work(claim_id, uuid.uuid4().hex)


def run_queue(run_id: int, limit: int) -> None:
    """Run the queue agent, which closes the run itself if it fails."""
    try:
        queue_run(run_id, limit, uuid.uuid4().hex)
    except Exception:
        log.exception("The queue run %s failed", run_id)
