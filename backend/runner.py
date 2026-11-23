"""Starting the agent on claims, one run at a time."""

import threading

from fastapi import HTTPException

from agent import main as agent
from backend.claims import list_summaries
from backend.db import now, session
from backend.decisions import record_step
from backend.models import RunStatus, StepIn
from backend.records import find_decision, load


def run_agent(claim_id: str, thread_id: str) -> str:
    """Run the agent on one claim. Tests replace this with a stub."""
    return agent.run(claim_id, thread_id)


def begin(claim_id: str) -> int:
    """Record that a run has started on a claim, which makes it in progress."""
    with session() as conn:
        cursor = conn.execute(
            "INSERT INTO runs (claim_id, status, started_at) VALUES (?, 'running', ?)",
            (claim_id, now()),
        )
    return cursor.lastrowid or 0


def execute(run_id: int, claim_id: str):
    """Run the agent on a claim and record how the run ended."""
    try:
        run_agent(claim_id, f"{claim_id}-{run_id}")
        problem = ""
    except Exception as error:  # noqa: BLE001
        problem = f"The agent stopped: {type(error).__name__}: {error}"
    with session() as conn:
        if not problem and not find_decision(conn, claim_id):
            problem = "The agent finished without recording a decision."
        conn.execute(
            "UPDATE runs SET status = ? WHERE run_id = ?",
            ("failed" if problem else "finished", run_id),
        )
        if problem:
            record_step(conn, claim_id, StepIn(kind="error", text=problem))


class Runner:
    """Runs the agent in a background thread, never two runs at once."""

    def __init__(self):
        self.lock = threading.Lock()
        self.claim_id: str | None = None
        self.thread: threading.Thread | None = None

    def status(self) -> RunStatus:
        return RunStatus(active=self.lock.locked(), claim_id=self.claim_id)

    def start(self, claim_ids: list[str]) -> RunStatus:
        """Start running the agent on each claim in turn."""
        if not self.lock.acquire(blocking=False):
            raise HTTPException(409, "A run is already active")
        self.claim_id = claim_ids[0]
        first_run = begin(claim_ids[0])
        self.thread = threading.Thread(
            target=self.work, args=(claim_ids, first_run), daemon=True
        )
        self.thread.start()
        return self.status()

    def work(self, claim_ids: list[str], first_run: int):
        try:
            for index, claim_id in enumerate(claim_ids):
                self.claim_id = claim_id
                execute(first_run if index == 0 else begin(claim_id), claim_id)
        finally:
            self.claim_id = None
            self.lock.release()


RUNNER = Runner()


def start_claim_run(claim_id: str) -> RunStatus:
    """Start a run on one claim that has no decision yet."""
    with session() as conn:
        load(conn, "claims", "claim_id", claim_id)
        if find_decision(conn, claim_id):
            raise HTTPException(409, f"{claim_id} already has a decision")
    return RUNNER.start([claim_id])


def start_queue_run() -> RunStatus:
    """Start a run on every waiting claim, one after another."""
    with session() as conn:
        waiting = [c.claim_id for c in list_summaries(conn) if c.state == "waiting"]
    if not waiting:
        raise HTTPException(409, "No claims are waiting")
    return RUNNER.start(waiting)
