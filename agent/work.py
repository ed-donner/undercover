"""How the queue works one claim: attempts, retries and giving up.

This is plain code, not left to the model: a claim is never decided twice,
a failed claim starts afresh, and it is left for a handler after two failures.
A claim that was stopped, not failed, carries on and it is not a new attempt.
"""

from collections.abc import Callable

from agent import api

MAX_ATTEMPTS = 2


def _attempt(
    run_id: int, claim_id: str, decide: Callable[[str], str], carrying_on: bool
) -> tuple[bool, str]:
    """Try to decide a claim once: (True, outcome) if settled, else (False, error).

    A claim being carried on after a stop is the attempt already counted.
    """
    if not carrying_on:
        api.update_run_item(run_id, claim_id, "in progress", "")
    try:
        return True, decide(claim_id)
    except Exception as error:  # noqa: BLE001 - any failure sends the claim back
        if api.get_claim(claim_id)["decision"] is not None:
            return True, "Decided (the result arrived after a failed attempt)."
        api.requeue_claim(claim_id)
        return False, str(error)


def work_claim(run_id: int, claim_id: str, decide: Callable[[str], str]) -> str:
    """Decide one claim, keeping its to-do item current, and say what happened."""
    item = next(i for i in api.get_current_run()["items"] if i["claim_id"] == claim_id)
    carrying_on = item["status"] == "in progress"
    attempts_made = item["attempts"] - carrying_on
    note = item["note"] or ""
    for attempt in range(attempts_made + 1, MAX_ATTEMPTS + 1):
        settled, note = _attempt(
            run_id, claim_id, decide, carrying_on and attempt == attempts_made + 1
        )
        if settled:
            api.update_run_item(run_id, claim_id, "done", note)
            return note
        if attempt < MAX_ATTEMPTS:
            failed = f"Attempt {attempt} failed: {note}"
            api.update_run_item(run_id, claim_id, "to do", failed)
    note = f"Left for a handler after {MAX_ATTEMPTS} failed attempts: {note}"
    api.update_run_item(run_id, claim_id, "left for a handler", note)
    return note
