"""Start a run and follow it: uv run -m agent --cap 5, or uv run -m agent CLM-1001."""

import argparse
import sys
import time

from agent.common import api, call

POLL_SECONDS = 2


def follow(run_id: int) -> None:
    """Print each change to the run's to-do list, then its summary."""
    shown: dict[str, str] = {}
    while True:
        run = api("GET", f"/api/runs/{run_id}")
        for todo in run["todos"]:
            if shown.get(todo["claim_id"]) != todo["status"]:
                shown[todo["claim_id"]] = todo["status"]
                print(f"{todo['claim_id']}: {todo['status']}  {todo['content']}")
        if run["status"] != "running":
            print(f"Run {run_id} {run['status']}: {run['summary'] or run['problem']}")
            return
        time.sleep(POLL_SECONDS)


def main(argv: list[str]) -> None:
    """Start a run of the queue up to a cap, or on one claim, through the backend."""
    parser = argparse.ArgumentParser(prog="uv run -m agent")
    parser.add_argument("claim_id", nargs="?", help="work this one claim")
    parser.add_argument("--cap", type=int, help="work the queue, up to this many")
    args = parser.parse_args(argv)
    if (args.claim_id is None) == (args.cap is None):
        parser.error("give either a claim id or --cap")
    started = (
        call("POST", f"/api/claims/{args.claim_id}/run")
        if args.claim_id
        else call("POST", "/api/runs", {"cap": args.cap})
    )
    if started.startswith("Refused"):
        print(started)
        return
    follow(api("GET", "/api/runs/latest")["id"])


if __name__ == "__main__":
    main(sys.argv[1:])
