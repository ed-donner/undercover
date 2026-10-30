from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from agent import queue
from backend.main import app


class StubModel(GenericFakeChatModel):
    """A chat model that gives scripted replies in place of a real model."""

    def bind_tools(self, tools, **kwargs):
        return self


def test_work_claim_retries_once_then_succeeds(monkeypatch):
    monkeypatch.setattr(queue, "backend", lambda: TestClient(app))
    attempts = []

    def fake_decide(claim_id: str, thread_id: str) -> str:
        attempts.append(claim_id)
        if len(attempts) == 1:
            TestClient(app).post(f"/api/claims/{claim_id}/steps", json={"text": "x"})
            raise RuntimeError("boom")
        TestClient(app).post(
            f"/api/claims/{claim_id}/decision",
            json={
                "decision": "approve",
                "payout": 100.0,
                "reason": "Stubbed.",
                "policy_reference": "Section 1",
            },
        )
        return "Approved for $100.00."

    monkeypatch.setattr(queue, "decide_one_claim", fake_decide)
    run = TestClient(app).post("/api/runs", json={"claim_ids": ["CLM-1001"]}).json()

    outcome = queue.work_one_claim(run["run_id"], "CLM-1001")

    assert outcome == "Approved for $100.00."
    assert len(attempts) == 2
    assert TestClient(app).get("/api/claims/CLM-1001").json()["status"] == "decided"
    item = TestClient(app).get("/api/runs/current").json()["items"][0]
    assert item["status"] == "done"
    assert item["attempts"] == 2


def test_work_claim_leaves_for_a_handler_after_two_failures(monkeypatch):
    monkeypatch.setattr(queue, "backend", lambda: TestClient(app))

    def fake_decide(claim_id: str, thread_id: str) -> str:
        TestClient(app).post(f"/api/claims/{claim_id}/steps", json={"text": "x"})
        raise RuntimeError("boom")

    monkeypatch.setattr(queue, "decide_one_claim", fake_decide)
    run = TestClient(app).post("/api/runs", json={"claim_ids": ["CLM-1001"]}).json()

    outcome = queue.work_one_claim(run["run_id"], "CLM-1001")

    assert "left for a handler" in outcome.lower()
    assert TestClient(app).get("/api/claims/CLM-1001").json()["status"] == "waiting"
    item = TestClient(app).get("/api/runs/current").json()["items"][0]
    assert item["status"] == "left for a handler"
    assert item["attempts"] == 2


def test_work_claim_is_not_retried_once_already_decided(monkeypatch):
    monkeypatch.setattr(queue, "backend", lambda: TestClient(app))
    attempts = []

    def fake_decide(claim_id: str, thread_id: str) -> str:
        attempts.append(claim_id)
        TestClient(app).post(
            f"/api/claims/{claim_id}/decision",
            json={
                "decision": "approve",
                "payout": 50.0,
                "reason": "Stubbed.",
                "policy_reference": "Section 1",
            },
        )
        raise RuntimeError("dropped on the way back")

    monkeypatch.setattr(queue, "decide_one_claim", fake_decide)
    run = TestClient(app).post("/api/runs", json={"claim_ids": ["CLM-1001"]}).json()

    outcome = queue.work_one_claim(run["run_id"], "CLM-1001")

    assert len(attempts) == 1
    assert "decided" in outcome.lower()
    item = TestClient(app).get("/api/runs/current").json()["items"][0]
    assert item["status"] == "done"


def test_finish_run_tool_reports_what_is_outstanding(monkeypatch):
    monkeypatch.setattr(queue, "backend", lambda: TestClient(app))
    run = (
        TestClient(app)
        .post("/api/runs", json={"claim_ids": ["CLM-1001", "CLM-1002"]})
        .json()
    )
    get_to_do, work_claim_tool, finish_run_tool = queue.queue_tools(run["run_id"])

    result = finish_run_tool.invoke({"summary": "x"})

    assert "Not finished" in result
    assert "CLM-1001" in result
    assert "CLM-1002" in result


def test_run_queue_works_a_capped_to_do_list(monkeypatch):
    monkeypatch.setattr(queue, "backend", lambda: TestClient(app))

    def fake_decide(claim_id: str, thread_id: str) -> str:
        TestClient(app).post(
            f"/api/claims/{claim_id}/decision",
            json={
                "decision": "approve",
                "payout": 100.0,
                "reason": "Stubbed.",
                "policy_reference": "Section 1",
            },
        )
        return f"Approved {claim_id} for $100.00."

    monkeypatch.setattr(queue, "decide_one_claim", fake_decide)

    all_claims = TestClient(app).get("/api/claims").json()
    first_id, second_id = (c["claim_id"] for c in all_claims[:2])
    other_id = all_claims[2]["claim_id"]

    replies = [
        AIMessage(
            content="", tool_calls=[{"name": "get_to_do", "args": {}, "id": "1"}]
        ),
        AIMessage(
            content="",
            tool_calls=[
                {"name": "work_claim", "args": {"claim_id": first_id}, "id": "2"}
            ],
        ),
        AIMessage(
            content="",
            tool_calls=[
                {"name": "work_claim", "args": {"claim_id": second_id}, "id": "3"}
            ],
        ),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "finish_run",
                    "args": {"summary": "Worked 2 claims."},
                    "id": "4",
                }
            ],
        ),
        AIMessage(content="Done. Worked 2 claims."),
    ]

    result = queue.run_queue(cap=2, llm=StubModel(messages=iter(replies)))

    assert result == "Done. Worked 2 claims."
    run = TestClient(app).get("/api/runs/current").json()
    assert run["summary"] == "Worked 2 claims."
    assert run["finished_on"] is not None
    assert {item["claim_id"] for item in run["items"]} == {first_id, second_id}
    assert all(item["status"] == "done" for item in run["items"])

    claims = {
        c["claim_id"]: c["status"] for c in TestClient(app).get("/api/claims").json()
    }
    assert claims[first_id] == "decided"
    assert claims[second_id] == "decided"
    assert claims[other_id] == "waiting"
