"""How the queue works one claim: attempts, retries and giving up.

This is plain code, not left to the model: a claim is never decided twice,
a failed claim starts afresh, and it is left for a handler after two failures.
A referred claim is left for a handler too.
A claim that was stopped, not failed, carries on and it is not a new attempt.
"""

from collections.abc import Callable
from decimal import Decimal

from agent import api
from agent.api import WAITING_FOR_SIGN_OFF

MAX_ATTEMPTS = 2


def _attempt(
    run_id: int, claim_id: str, decide: Callable[[str], str], carrying_on: bool
) -> str | None:
    """Try to decide a claim once: None if it is decided, else the error.

    A claim being carried on after a stop is the attempt already counted.
    """
    if not carrying_on:
        api.update_run_item(run_id, claim_id, "in progress", "")
    try:
        decide(claim_id)
    except Exception as error:  # noqa: BLE001 - any failure sends the claim back
        if api.get_claim(claim_id)["decision"] is not None:
            return None
        api.requeue_claim(claim_id)
        return " ".join(str(error).split())
    return None


def _settle(run_id: int, claim_id: str) -> str:
    """Close a decided claim's to-do item with a one-line outcome.

    A referral needs a handler's judgment, so it is left for one.
    """
    claim = api.get_claim(claim_id)
    match claim["decision"]:
        case "approve":
            note = f"Approved ${Decimal(claim['payout']):,.2f}"
            if claim["status"] == WAITING_FOR_SIGN_OFF:
                note += ", waiting for sign-off"
        case "decline":
            note = "Declined"
        case _:
            note = "Referred"
    status = "left for a handler" if claim["decision"] == "refer" else "done"
    api.update_run_item(run_id, claim_id, status, note)
    return note


def work_claim(run_id: int, claim_id: str, decide: Callable[[str], str]) -> str:
    """Decide one claim, keeping its to-do item current, and say what happened."""
    item = next(i for i in api.get_current_run()["items"] if i["claim_id"] == claim_id)
    carrying_on = item["status"] == "in progress"
    attempts_made = item["attempts"] - carrying_on
    error = item["note"] or ""
    for attempt in range(attempts_made + 1, MAX_ATTEMPTS + 1):
        failure = _attempt(
            run_id, claim_id, decide, carrying_on and attempt == attempts_made + 1
        )
        if failure is None:
            return _settle(run_id, claim_id)
        error = failure
        if attempt < MAX_ATTEMPTS:
            failed = f"Attempt {attempt} failed: {error}"
            api.update_run_item(run_id, claim_id, "to do", failed)
    note = f"Left for a handler after {MAX_ATTEMPTS} failed attempts: {error}"
    api.update_run_item(run_id, claim_id, "left for a handler", note)
    return note
