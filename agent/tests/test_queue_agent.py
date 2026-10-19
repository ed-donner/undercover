import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from agent import harness, queue_agent
from agent.main import run_claim, run_queue
from agent.tests.conftest import Down, StubModel, call, down_after, flaky, stub
from backend import runner


def decline(claim_id: str) -> AIMessage:
    return call(
        "record_decision",
        claim_id=claim_id,
        decision="decline",
        payout=0,
        explanation="Not covered.",
        policy_section="Section 9, General exclusions",
    )


def work(claim_id: str) -> AIMessage:
    return call("work_claim", claim_id=claim_id)


def todos(*items: tuple[str, str]) -> AIMessage:
    return call(
        "write_todos",
        todos=[{"text": text, "status": status} for text, status in items],
    )


def start_run(client: TestClient, limit: int) -> int:
    return client.post("/api/runs", json={"limit": limit}).json()["run_id"]


def statuses(client: TestClient) -> dict[str, str]:
    claims = client.get("/api/claims").json()
    return {claim["claim_id"]: claim["status"] for claim in claims}


def count(client: TestClient, status: str) -> int:
    return list(statuses(client).values()).count(status)


def steps(client: TestClient, claim_id: str) -> list[dict]:
    return client.get(f"/api/claims/{claim_id}/steps").json()


def run(
    client: TestClient, limit: int, queue: StubModel, claims: StubModel | None = None
) -> str:
    run_id = start_run(client, limit)
    return queue_agent.queue_run(run_id, limit, "thread", queue, claims)


def test_the_queue_agent_has_four_tools():
    tools = queue_agent.queue_tools(1, None)
    assert {tool.name for tool in tools} == {
        "list_waiting_claims",
        "write_todos",
        "work_claim",
        "check_queue",
    }


def test_tools_show_waiting_claims_and_what_was_missed(client: TestClient):
    start_run(client, 2)
    first, _, work_claim, check = queue_agent.queue_tools(1, None)
    client.post("/api/claims/CLM-1001/start")
    listed = first.invoke({})
    assert "CLM-1002" in listed
    assert "CLM-1001" not in listed
    assert "story" not in listed
    assert check.invoke({}).count("claim_id") == 2
    assert work_claim.invoke({"claim_id": "CLM-1001"}).startswith("Error 409")


def test_a_run_with_a_to_do_list_and_a_summary(client: TestClient):
    queue = stub(
        call("list_waiting_claims"),
        todos(("CLM-1001", "todo"), ("CLM-1002", "todo")),
        todos(("CLM-1001", "in_progress"), ("CLM-1002", "todo")),
        work("CLM-1001"),
        todos(("CLM-1001", "done"), ("CLM-1002", "in_progress")),
        work("CLM-1002"),
        todos(("CLM-1001", "done"), ("CLM-1002", "done")),
        call("check_queue"),
        AIMessage(content="Worked two claims."),
    )
    claims = stub(decline("CLM-1001"), AIMessage(content="No."), decline("CLM-1002"))
    summary = run(client, 2, queue, claims)
    assert summary == "Worked two claims."
    latest = client.get("/api/runs/latest").json()
    assert latest["status"] == "finished"
    assert latest["summary"] == "Worked two claims."
    assert [todo["status"] for todo in latest["todos"]] == ["done", "done"]
    assert count(client, "decided") == 2


def test_the_cap_cannot_be_passed(client: TestClient):
    names = ["CLM-1001", "CLM-1002", "CLM-1003", "CLM-1004", "CLM-1005"]
    queue = stub(*[work(name) for name in names], AIMessage(content="Done."))
    claims = stub(
        *[m for name in names[:3] for m in (decline(name), AIMessage(content="No."))]
    )
    run(client, 3, queue, claims)
    assert count(client, "decided") == 3
    assert count(client, "waiting") == 22
    assert [statuses(client)[name] for name in names[3:]] == ["waiting", "waiting"]


def test_one_bad_claim_does_not_stop_the_run_and_is_tried_again(client: TestClient):
    queue = stub(
        work("CLM-1001"),
        work("CLM-1002"),
        work("CLM-1001"),
        AIMessage(content="Done."),
    )
    claims = flaky(
        decline("CLM-1002"),
        AIMessage(content="No."),
        decline("CLM-1001"),
        AIMessage(content="No."),
        failures=3,
    )
    assert run(client, 2, queue, claims) == "Done."
    assert count(client, "decided") == 2
    assert count(client, "in_progress") == 0
    first = steps(client, "CLM-1001")
    assert [step["kind"] for step in first[:2]] == ["error", "error"]
    assert first[1]["text"].startswith("Failed 1 of 2 tries: back in the queue.")


def test_a_claim_that_fails_twice_is_left_for_a_handler(client: TestClient):
    queue = stub(work("CLM-1001"), work("CLM-1001"), AIMessage(content="Done."))
    run(client, 1, queue, StubModel(messages=Down()))
    assert statuses(client)["CLM-1001"] == "needs_handler"
    assert [step["kind"] for step in steps(client, "CLM-1001")] == ["error"] * 4


def test_a_retry_does_not_use_the_cap_twice(client: TestClient):
    run_id = start_run(client, 1)
    list_waiting, _, work_claim, _ = queue_agent.queue_tools(
        run_id, StubModel(messages=Down())
    )
    assert "back in the queue" in work_claim.invoke({"claim_id": "CLM-1001"})
    second = queue_agent.queue_tools(
        run_id, stub(decline("CLM-1001"), AIMessage(content="No."))
    )[2]
    assert second.invoke({"claim_id": "CLM-1001"}) == "CLM-1001: declined."
    assert second.invoke({"claim_id": "CLM-1002"}).startswith("Error 409")
    assert "CLM-1001" not in list_waiting.invoke({})


def test_a_claim_left_for_a_handler_is_not_offered_again(client: TestClient):
    run_id = start_run(client, 5)
    list_waiting, _, work_claim, check = queue_agent.queue_tools(
        run_id, StubModel(messages=Down())
    )
    work_claim.invoke({"claim_id": "CLM-1001"})
    work_claim.invoke({"claim_id": "CLM-1001"})
    assert statuses(client)["CLM-1001"] == "needs_handler"
    assert "CLM-1001" not in list_waiting.invoke({})
    assert "CLM-1001" not in check.invoke({})


def test_a_second_work_claim_changes_nothing(client: TestClient):
    run_id = start_run(client, 5)
    _, _, work_claim, _ = queue_agent.queue_tools(
        run_id, stub(decline("CLM-1001"), AIMessage(content="No."))
    )
    work_claim.invoke({"claim_id": "CLM-1001"})
    assert work_claim.invoke({"claim_id": "CLM-1001"}).startswith("Error 409")
    assert (
        client.get("/api/claims/CLM-1001").json()["decision"]["decision"] == "decline"
    )


def test_the_agent_is_sent_back_when_it_missed_a_claim(client: TestClient):
    queue = stub(
        AIMessage(content="I am done."),
        work("CLM-1001"),
        AIMessage(content="Now I am done."),
    )
    claims = stub(decline("CLM-1001"), AIMessage(content="No."))
    summary = run(client, 1, queue, claims)
    assert summary == "Now I am done."
    assert statuses(client)["CLM-1001"] == "decided"


def test_the_agent_is_sent_back_only_a_few_times(client: TestClient):
    queue = stub(*[AIMessage(content="Done.")] * 5)
    assert run(client, 1, queue) == "Done."
    assert statuses(client)["CLM-1001"] == "waiting"


def test_a_queue_agent_that_fails_ends_the_run_as_failed(client: TestClient):
    queue = down_after(work("CLM-1001"))
    claims = stub(decline("CLM-1001"), AIMessage(content="No."))
    run_id = start_run(client, 2)
    with pytest.raises(RuntimeError, match="The model is down"):
        queue_agent.queue_run(run_id, 2, "thread", queue, claims)
    latest = client.get("/api/runs/latest").json()
    assert latest["status"] == "failed"
    assert latest["summary"] == "The run failed: RuntimeError: The model is down"
    assert count(client, "in_progress") == 0
    assert statuses(client)["CLM-1001"] == "decided"


def test_the_command_line_runs_a_claim_and_a_queue(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        "agent.main.queue_run", lambda run_id, limit, _: f"run {run_id}, limit {limit}"
    )
    assert run_queue(7) == "run 1, limit 7"
    client.post("/api/runs/1/finish", json={"summary": "", "status": "finished"})
    assert run_queue(None) == "run 2, limit 25"
    assert harness.request("GET", "/api/runs/latest").json()["limit"] == 25
    monkeypatch.setattr(
        "agent.main.work", lambda claim_id, thread_id: f"worked {claim_id}"
    )
    assert run_claim("CLM-1001") == "worked CLM-1001"
    assert statuses(client)["CLM-1001"] == "in_progress"


def test_the_backend_runs_the_queue_in_the_background(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    seen: list[tuple[int, int]] = []

    def queue(run_id: int, limit: int, thread_id: str) -> str:
        seen.append((run_id, limit))
        return "Done."

    monkeypatch.setattr(runner, "queue_run", queue)
    response = client.post("/api/queue/run", json={"limit": 5})
    assert response.status_code == 202
    assert response.json()["limit"] == 5
    assert seen == [(1, 5)]
    assert client.post("/api/queue/run", json={"limit": 0}).status_code == 422
    assert client.post("/api/queue/run", json={"limit": 5}).status_code == 409


def test_a_failed_background_run_is_logged_not_raised(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    def broken(run_id: int, limit: int, thread_id: str) -> str:
        raise RuntimeError("The model is down")

    monkeypatch.setattr(runner, "queue_run", broken)
    assert client.post("/api/queue/run", json={"limit": 5}).status_code == 202
