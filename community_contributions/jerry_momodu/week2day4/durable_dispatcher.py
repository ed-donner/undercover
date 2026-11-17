"""The dispatcher from the Week 2 Day 4 assignment, saved to Supabase with PostgresSaver.

The stretch challenge restarts the kernel while the claim agents are working. To do that
reliably, the notebook runs this file as a separate process, kills it partway through the
run, and then resumes the same thread. Killing the process wipes everything in memory, just
as restarting the kernel does.

The claim agent here is a slow stand-in, so the experiment costs nothing. It appends a line to
a log file each time it starts or finishes a claim, so we can see which claims were worked
before the kill and which were worked again after it.

There are two ways to cap the swarm at 5 claim agents, and they behave differently after a kill:

- "pool": max_concurrency=5, as in the lab. LangGraph runs the claim agents and the saves of
  their results on one thread pool of that size, so a finished claim's result waits in the
  queue behind the claims still to run. Killed partway through, nothing finished is saved.
- "semaphore": max_concurrency=30, more threads than claims, so each result is saved as soon
  as its claim finishes, and a semaphore inside the node lets only 5 claims work at once.

Usage:
    python durable_dispatcher.py run <thread_id> <log_file> <pool|semaphore>
    python durable_dispatcher.py resume <thread_id> <log_file> <pool|semaphore>
"""

import json
import operator
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Annotated, TypedDict

import psycopg
from dotenv import load_dotenv
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy, Send
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[3]
CLAIMS = json.loads((ROOT / "data/evals/harder/claims.json").read_text(encoding="utf-8"))
SECONDS_PER_CLAIM = 4
AGENTS_AT_ONCE = 5
THREADS_FOR_SEMAPHORE = 30

log_file: Path | None = None
log_lock = threading.Lock()
agents = threading.Semaphore(AGENTS_AT_ONCE)


class ScoredDispatch(TypedDict):
    """What the dispatcher keeps for one run, with the run's scores."""

    claims: list[str]
    results: Annotated[list, operator.add]
    scores: dict


def log(event, claim_id):
    """Append one line to the log file, so another process can follow the run.

    The claim agents run on threads, and appends from several threads can be lost on Windows,
    so one lock lets one thread write at a time.
    """
    if log_file:
        line = {"event": event, "claim_id": claim_id, "pid": os.getpid(), "at": datetime.now().isoformat()}
        with log_lock, log_file.open("a", encoding="utf-8") as file:
            file.write(json.dumps(line) + "\n")


def list_claims(state: ScoredDispatch):
    """The claims to work in this run."""
    return {"claims": [claim["claim_id"] for claim in CLAIMS]}


def fan_out(state: ScoredDispatch):
    """Send each claim to a claim agent."""
    return [Send("work_claim", claim_id) for claim_id in state["claims"]]


def slow_stand_in(claim_id):
    """Pretend to work a claim for a few seconds, and log when it starts and finishes."""
    with agents:
        return work(claim_id)


def work(claim_id):
    """The stand-in's work on one claim."""
    log("started", claim_id)
    started = datetime.now()
    time.sleep(SECONDS_PER_CLAIM)
    log("finished", claim_id)
    return {"results": [{"claim_id": claim_id, "pid": os.getpid(), "started": started, "finished": datetime.now()}]}


def score_run(state: ScoredDispatch):
    """Score the whole run once every claim agent has finished."""
    results = state["results"]
    seconds = [(result["finished"] - result["started"]).total_seconds() for result in results]
    run_seconds = (max(r["finished"] for r in results) - min(r["started"] for r in results)).total_seconds()
    log("scored", None)
    return {"scores": {
        "claims": len(results),
        "processes": len({result["pid"] for result in results}),
        "seconds": run_seconds,
        "slowest_claim": max(seconds),
        "seconds_per_claim": sum(seconds) / len(seconds),
    }}


def connect():
    """Connect to Supabase as Day 3 does, with the lab's own schema."""
    load_dotenv(ROOT / ".env", override=True)
    connection = psycopg.connect(
        os.environ["DATABASE_URL"], autocommit=True, prepare_threshold=0, row_factory=dict_row,
        options="-c search_path=lab",
    )
    connection.execute("CREATE SCHEMA IF NOT EXISTS lab")
    return connection


def build(checkpointer):
    """The dispatcher with a score_run node after the claim agents, saved by the checkpointer."""
    builder = StateGraph(ScoredDispatch)
    builder.add_node("list_claims", list_claims)
    builder.add_node("work_claim", slow_stand_in, retry_policy=RetryPolicy(max_attempts=3))
    builder.add_node("score_run", score_run)
    builder.add_edge(START, "list_claims")
    builder.add_conditional_edges("list_claims", fan_out, ["work_claim"])
    builder.add_edge("work_claim", "score_run")
    builder.add_edge("score_run", END)
    return builder.compile(checkpointer=checkpointer)


def run_config(thread_id, cap):
    """The config for a run: its thread, and how the swarm is capped at 5 claim agents."""
    global agents
    if cap == "pool":
        agents = threading.Semaphore(THREADS_FOR_SEMAPHORE)
        max_concurrency = AGENTS_AT_ONCE
    else:
        agents = threading.Semaphore(AGENTS_AT_ONCE)
        max_concurrency = THREADS_FOR_SEMAPHORE
    return {"configurable": {"thread_id": thread_id}, "max_concurrency": max_concurrency}


def main(command, thread_id, log_path, cap):
    """Start a run on a thread, or resume the thread from its last checkpoint."""
    global log_file
    log_file = Path(log_path)
    with connect() as connection:
        checkpointer = PostgresSaver(connection)
        checkpointer.setup()
        dispatcher = build(checkpointer)
        config = run_config(thread_id, cap)
        result = dispatcher.invoke({} if command == "run" else None, config)
        print(json.dumps(result["scores"]))


if __name__ == "__main__":
    main(*sys.argv[1:5])
