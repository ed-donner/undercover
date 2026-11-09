"""The statuses a claim and a run's to-do item can have, written once."""

from enum import StrEnum


class ClaimStatus(StrEnum):
    """Where a claim stands in the queue."""

    WAITING = "waiting"
    IN_PROGRESS = "in progress"
    WAITING_FOR_SIGN_OFF = "waiting for sign-off"
    DECIDED = "decided"


class ItemStatus(StrEnum):
    """Where a to-do item on a run stands."""

    TO_DO = "to do"
    IN_PROGRESS = "in progress"
    DONE = "done"
    LEFT_FOR_A_HANDLER = "left for a handler"
