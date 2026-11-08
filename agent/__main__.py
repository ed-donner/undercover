"""Run the Shoppie Agent from the terminal: one named request, or a capped run."""

import argparse
import time

from agent import main as agent

POLL_SECONDS = 3


def run_capped(cap: int) -> str:
    """Start a run through the backend, wait for it to end and return its summary."""
    with agent.backend() as client:
        client.post("/api/runs", json={"cap": cap}).raise_for_status()
        while (run := client.get("/api/runs/current").json())["status"] == "running":
            time.sleep(POLL_SECONDS)
    return f"{run['run_id']} {run['status']}: {run['summary']}"


def main() -> None:
    """Parse the arguments and run the agent."""
    parser = argparse.ArgumentParser(prog="uv run -m agent")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("request_id", nargs="?", help="work one request, e.g. REQ-7001")
    target.add_argument("--cap", type=int, help="work the queue, up to this many")
    args = parser.parse_args()
    if args.request_id:
        print(agent.work_request(args.request_id)["line"])
    else:
        print(run_capped(args.cap))


if __name__ == "__main__":
    main()
