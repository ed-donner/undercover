"""Running the agent on claims in the background."""

import logging
import uuid
from contextlib import closing

from agent.main import run as run_agent
from backend import workflow
from backend.db import connect

log = logging.getLogger(__name__)


def run_claim(claim_id: str) -> None:
    run_agent(claim_id, uuid.uuid4().hex)


def run_waiting() -> None:
    """Work the waiting claims one at a time until none are left."""
    while True:
        with closing(connect()) as db:
            claim_id = workflow.claim_next_waiting(db)
        if claim_id is None:
            return
        try:
            run_claim(claim_id)
        except Exception:
            log.exception("The agent failed on %s", claim_id)
