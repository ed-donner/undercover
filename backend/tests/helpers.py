"""Explicit queue contracts shared by workflow tests."""

from contextlib import contextmanager

import httpx

from agent.api import BackendAPI
from backend.documents import Documents, ReadInput
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


def read_sources(store, run_id, claim_id="CLM-1001"):
    documents = Documents(store)
    for document_id, sections in (("wording", [3, 10]), ("manual", [4, 9])):
        for section in sections:
            documents.read(
                claim_id,
                ReadInput(run_id=run_id, document_id=document_id, section=section),
            )


def http_backend(client):
    def forward(request):
        response = client.request(
            request.method,
            str(request.url),
            content=request.content,
            headers=request.headers,
        )
        return httpx.Response(
            response.status_code,
            content=response.content,
            headers=response.headers,
            request=request,
        )

    return httpx.Client(
        base_url="http://testserver", transport=httpx.MockTransport(forward)
    )


@contextmanager
def agent_backend(client):
    with http_backend(client) as transport:
        yield BackendAPI(transport)
