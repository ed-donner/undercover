"""A claim's lease: one agent works a claim at a time.

The lease is renewed in the background while the claim is worked, so it runs
out soon after an agent dies and the next run can carry the claim on.
"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from threading import Event, Thread

from agent import api

RENEWALS_PER_LEASE = 3


@contextmanager
def held(claim_id: str) -> Iterator[bool]:
    """Hold a claim's lease inside the block; yield False if another agent has it."""
    owner = uuid.uuid4().hex
    seconds = api.acquire_lease(claim_id, owner)
    if seconds is None:
        yield False
        return
    done = Event()
    renewer = Thread(target=_renew, args=(claim_id, owner, seconds, done))
    renewer.start()
    try:
        yield True
    finally:
        done.set()
        renewer.join()
        api.release_lease(claim_id, owner)


def _renew(claim_id: str, owner: str, seconds: int, done: Event) -> None:
    while not done.wait(seconds / RENEWALS_PER_LEASE):
        api.acquire_lease(claim_id, owner)
