"""How the queue works one claim: attempts, retries and giving up.

This is plain code, not left to the model: a claim is never decided twice,
never stays stuck in progress, and is left for a handler after two failures.
"""

from collections.abc import Callable

from agent import api

MAX_ATTEMPTS = 2
SETTLED_CLAIM_STATUSES = {"decided", "waiting for sign-off"}


def _attempt(
    run_id: int, claim_id: str, decide: Callable[[str], str]
) -> tuple[bool, str]:
    """Try to decide a claim once: (True, outcome) if settled, else (False, error)."""
    api.update_run_item(run_id, claim_id, "in progress", "")
    try:
        return True, decide(claim_id)
    except Exception as error:  # noqa: BLE001 - any failure sends the claim back
        if api.get_claim(claim_id)["status"] in SETTLED_CLAIM_STATUSES:
            return True, "Decided (the result arrived after a failed attempt)."
        api.requeue_claim(claim_id)
        return False, str(error)


def work_claim(run_id: int, claim_id: str, decide: Callable[[str], str]) -> str:
    """Decide one claim, keeping its to-do item current, and say what happened."""
    note = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        settled, note = _attempt(run_id, claim_id, decide)
        if settled:
            api.update_run_item(run_id, claim_id, "done", note)
            return note
        if attempt < MAX_ATTEMPTS:
            failed = f"Attempt {attempt} failed: {note}"
            api.update_run_item(run_id, claim_id, "to do", failed)
    note = f"Left for a handler after {MAX_ATTEMPTS} failed attempts: {note}"
    api.update_run_item(run_id, claim_id, "left for a handler", note)
    return note
