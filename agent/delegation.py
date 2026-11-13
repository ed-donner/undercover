"""Domain delegation and concise results; all transport stays in api.py."""

import time

from agent.api import BackendAPI

POLL_SECONDS = 0.25
DELEGATION_SECONDS = 490


def queue_context(api: BackendAPI, run_id: str) -> dict:
    state = api.run(run_id)
    keys = (
        "claim_id",
        "claim_type",
        "amount_claimed",
        "status",
        "needs_handler",
        "failures",
    )
    state["claims"] = [
        {key: claim[key] for key in keys}
        for claim in api.claims()
        if claim["claim_id"] in state["scope"]
    ]
    return state


def delegate(api: BackendAPI, parent_run_id: str, claim_id: str) -> str:
    current = api.run(parent_run_id)
    previous = next((t for t in current["tasks"] if t["claim_id"] == claim_id), None)
    if previous and previous["state"] in ("done", "needs_handler"):
        return f"{claim_id}: {previous['reason']}"
    run_id = api.start_attempt(claim_id, parent_run_id)["run_id"]
    deadline = time.monotonic() + DELEGATION_SECONDS
    while True:
        attempt = next(r for r in api.attempts(claim_id) if r["run_id"] == run_id)
        if attempt["status"] != "running":
            return summary(api.claim(claim_id))
        if time.monotonic() >= deadline:
            api.finish_attempt(run_id)
            return summary(api.claim(claim_id))
        time.sleep(POLL_SECONDS)


def summary(claim: dict) -> str:
    decision = claim["decision"]
    if decision is None:
        reason = (
            claim["handler_reason"]
            if claim["needs_handler"]
            else "failed; retry available"
        )
        return f"{claim['claim_id']}: {reason}"
    payment = "paid" if claim["payment"] else "unpaid"
    if claim["status"] == "waiting_for_sign_off":
        payment = "waiting for sign-off"
    return (
        f"{claim['claim_id']}: {decision['outcome']}, "
        f"${decision['payout']:,.2f}, {payment}"
    )
