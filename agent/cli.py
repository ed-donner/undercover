"""Command line for processing claims through the running backend."""

import time
from urllib.parse import quote

import httpx

from agent.main import backend

POLL_SECONDS = 1


def wait_for(client: httpx.Client, path: str, run_id: str) -> dict:
    while True:
        runs = client.get(f"{path}/runs").json()
        run = next(item for item in runs if item["run_id"] == run_id)
        if run["status"] != "running":
            return run
        time.sleep(POLL_SECONDS)


def summary(claim: dict) -> str:
    decision = claim["decision"]
    if decision["outcome"] != "approve":
        return decision["outcome"]
    paid = "paid" if claim["payment"] else "waiting for sign-off"
    return f"approve, ${decision['payout']:,.2f}, {paid}"


def process(client: httpx.Client, claim_id: str) -> tuple[str, bool]:
    path = f"/api/claims/{quote(claim_id, safe='')}"
    started = client.post(f"{path}/runs")
    if started.is_error:
        return f"not started ({started.status_code})", False
    run = wait_for(client, path, started.json()["run_id"])
    if run["status"] == "failed":
        return f"failed, {run['error']}", False
    return summary(client.get(path).json()), True


def main(claim_ids: list[str]) -> None:
    """Process the named claims, or every waiting claim, one at a time."""
    failed = False
    try:
        with backend() as client:
            ids = claim_ids or [
                claim["claim_id"]
                for claim in client.get("/api/claims").json()
                if claim["status"] == "waiting"
            ]
            if not ids:
                print("No waiting claims.")
            for claim_id in ids:
                line, ok = process(client, claim_id)
                failed = failed or not ok
                print(f"{claim_id}: {line}", flush=True)
    except httpx.ConnectError:
        raise SystemExit("Backend not reachable. Start it with npm run dev.") from None
    if failed:
        raise SystemExit(1)
