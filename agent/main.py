"""The UnderCover Agent from the command line.

uv run -m agent.main CLM-1001          works one waiting claim
uv run -m agent.main queue --limit 5   runs the queue agent on at most 5 claims
"""

import argparse
import uuid

from agent.claim_agent import work
from agent.harness import request
from agent.queue_agent import queue_run


def run_claim(claim_id: str) -> str:
    """Start a waiting claim, work it and return the claim agent's report."""
    request("POST", f"/api/claims/{claim_id}/start").raise_for_status()
    return work(claim_id, uuid.uuid4().hex)


def run_queue(limit: int | None) -> str:
    """Start a run of up to `limit` claims (all waiting if None); return its summary."""
    if limit is None:
        claims = request("GET", "/api/claims").json()
        limit = max(sum(c["status"] == "waiting" for c in claims), 1)
    run = request("POST", "/api/runs", {"limit": limit})
    run.raise_for_status()
    return queue_run(run.json()["run_id"], limit, uuid.uuid4().hex)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", help="a claim id, or 'queue'")
    parser.add_argument("--limit", type=int, help="the most claims a queue run takes")
    args = parser.parse_args()
    print(run_queue(args.limit) if args.target == "queue" else run_claim(args.target))
