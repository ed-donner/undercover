"""Explicit queue contracts shared by workflow tests."""

from backend.harness import Harness
from backend.harness_models import QueueStart, Task


def parent(store):
    harness = Harness(store)
    return next(
        (run for run in harness.history() if run.status == "running"),
        None,
    ) or harness.create(QueueStart(mode="queue", max_claims=None))


def start(client, claim_id="CLM-1001"):
    store = client.app.state.store
    run = parent(store)
    harness = Harness(store)
    tasks = [Task(claim_id=t.claim_id, state=t.state) for t in run.tasks]
    if claim_id in run.scope and claim_id not in {t.claim_id for t in tasks}:
        tasks.append(Task(claim_id=claim_id, state="todo"))
    harness.plan(run.run_id, tasks)
    return client.post(
        f"/api/claims/{claim_id}/runs", json={"parent_run_id": run.run_id}
    )


def start_workflow(workflow, claim_id="CLM-1001"):
    run = parent(workflow.store)
    tasks = [Task(claim_id=t.claim_id, state=t.state) for t in run.tasks]
    if claim_id not in {t.claim_id for t in tasks}:
        tasks.append(Task(claim_id=claim_id, state="todo"))
    Harness(workflow.store).plan(run.run_id, tasks)
    return workflow.start(claim_id, run.run_id)
