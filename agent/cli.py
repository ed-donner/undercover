"""Start one agent-led run and poll its persisted result."""

import argparse
import time

import httpx

from agent.main import backend

POLL_SECONDS = 1


def wait_for(client: httpx.Client, run_id: str) -> dict:
    while True:
        response = client.get(f"/api/agent-runs/{run_id}")
        response.raise_for_status()
        run = response.json()
        if run["status"] != "running":
            return run
        time.sleep(POLL_SECONDS)


def positive(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("Cap must be a positive integer")
    return number


def process(client: httpx.Client, request: dict) -> bool:
    response = client.post("/api/agent-runs", json=request)
    if response.is_error:
        print(f"Not started ({response.status_code}): {response.json()['detail']}")
        return False
    result = wait_for(client, response.json()["run_id"])
    print(result["summary"], flush=True)
    if result["error"]:
        print(result["error"], flush=True)
    return result["status"] == "completed" and not any(
        "failed" in task["reason"].lower() or "unresolved" in task["reason"].lower()
        for task in result["tasks"]
    )


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
        with backend() as client:
            for request in requests:
                failed = not process(client, request) or failed
    except httpx.ConnectError:
        raise SystemExit("Backend not reachable. Start it with npm run dev.") from None
    if failed:
        raise SystemExit(1)
