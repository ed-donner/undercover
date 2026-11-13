"""Start one agent-led run and poll its persisted result."""

import argparse
import time

import httpx

from agent import api

POLL_SECONDS = 1


def wait_for(backend: api.BackendAPI, run_id: str) -> dict:
    while True:
        run = backend.run(run_id)
        if run["status"] != "running":
            return run
        time.sleep(POLL_SECONDS)


def positive(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("Cap must be a positive integer")
    return number


def process(backend: api.BackendAPI, request: dict) -> bool:
    try:
        started = backend.start_run(request)
    except httpx.HTTPStatusError as error:
        print(
            f"Not started ({error.response.status_code}): "
            f"{error.response.json()['detail']}"
        )
        return False
    result = wait_for(backend, started["run_id"])
    print(result["summary"], flush=True)
    if result["error"]:
        print(result["error"], flush=True)
    return result["status"] == "completed" and result["technical_issues"] == 0


def main(arguments: list[str]) -> None:
    """Start the queue once, a capped trial, or explicit named-claim runs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("claim_ids", nargs="*")
    parser.add_argument("--max-claims", type=positive)
    args = parser.parse_args(arguments)
    if args.claim_ids and args.max_claims is not None:
        parser.error("--max-claims is only for queue runs")
    requests = (
        [{"mode": "claim", "claim_id": key} for key in args.claim_ids]
        if args.claim_ids
        else [{"mode": "queue", "max_claims": args.max_claims}]
    )
    failed = False
    try:
        with api.connect() as backend:
            for request in requests:
                failed = not process(backend, request) or failed
    except httpx.ConnectError:
        raise SystemExit("Backend not reachable. Start it with npm run dev.") from None
    if failed:
        raise SystemExit(1)
