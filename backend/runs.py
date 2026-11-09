"""A run's to-do list: one row per claim it works."""

from typing import Any

from sqlalchemy import func, insert, select, update

from backend import db, tables
from backend.errors import Conflict, NotFound
from backend.statuses import ItemStatus

SETTLED_STATUSES = {ItemStatus.DONE, ItemStatus.LEFT_FOR_A_HANDLER}


class RunNotReady(Conflict):
    """A run can't finish while items are still being worked."""


def get_run(run_id: int) -> dict[str, Any]:
    """Return one run with its items, or raise NotFound."""
    with db.connection() as conn:
        run = conn.execute(
            select(tables.runs).where(tables.runs.c.run_id == run_id)
        ).one_or_none()
        if run is None:
            raise NotFound(f"No run {run_id}")
        items = conn.execute(
            select(
                tables.run_items.c.claim_id,
                tables.run_items.c.status,
                tables.run_items.c.attempts,
                tables.run_items.c.note,
            )
            .where(tables.run_items.c.run_id == run_id)
            .order_by(tables.run_items.c.claim_id)
        )
        return {
            **run._mapping,
            "items": [dict(item._mapping) for item in items],
        }


def get_current_run() -> dict[str, Any] | None:
    """Return the most recently started run with its items, or None before the first."""
    with db.connection() as conn:
        run_id = conn.execute(select(func.max(tables.runs.c.run_id))).scalar_one()
    return None if run_id is None else get_run(run_id)


def start_run(claim_ids: list[str]) -> dict[str, Any]:
    """Start a run with one `to do` item per claim."""
    with db.connection() as conn:
        run_id = conn.execute(
            insert(tables.runs)
            .values(started_on=db.now())
            .returning(tables.runs.c.run_id)
        ).scalar_one()
        if claim_ids:
            conn.execute(
                insert(tables.run_items),
                [
                    {"run_id": run_id, "claim_id": claim_id, "status": ItemStatus.TO_DO}
                    for claim_id in claim_ids
                ],
            )
    return get_run(run_id)


def update_run_item(
    run_id: int, claim_id: str, status: str, note: str
) -> dict[str, Any]:
    """Update one run item's status and note; `in progress` counts as an attempt."""
    attempt = 1 if status == ItemStatus.IN_PROGRESS else 0
    with db.connection() as conn:
        updated = conn.execute(
            update(tables.run_items)
            .where(
                tables.run_items.c.run_id == run_id,
                tables.run_items.c.claim_id == claim_id,
            )
            .values(
                status=status, note=note, attempts=tables.run_items.c.attempts + attempt
            )
            .returning(
                tables.run_items.c.claim_id,
                tables.run_items.c.status,
                tables.run_items.c.attempts,
                tables.run_items.c.note,
            )
        ).one_or_none()
    if updated is None:
        raise NotFound(f"No item for claim {claim_id} in run {run_id}")
    return dict(updated._mapping)


def finish_run(run_id: int, summary: str) -> dict[str, Any]:
    """Finish a run, recording its summary.

    Raises RunNotReady if any item isn't `done` or `left for a handler`.
    """
    outstanding = [
        item["claim_id"]
        for item in get_run(run_id)["items"]
        if item["status"] not in SETTLED_STATUSES
    ]
    if outstanding:
        raise RunNotReady(f"Still outstanding: {', '.join(outstanding)}")
    with db.connection() as conn:
        conn.execute(
            update(tables.runs)
            .where(tables.runs.c.run_id == run_id)
            .values(finished_on=db.now(), summary=summary)
        )
    return get_run(run_id)
