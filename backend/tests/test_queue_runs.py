from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import app


def start_run(client: TestClient, limit: int = 5):
    return client.post("/api/runs", json={"limit": limit})


def take(client: TestClient, claim_id: str, run_id: int = 1):
    return client.post(f"/api/runs/{run_id}/claims/{claim_id}")


def start(client: TestClient, claim_id: str):
    return client.post(f"/api/claims/{claim_id}/start")


def fail(client: TestClient, claim_id: str, reason: str = "The model timed out"):
    return client.post(f"/api/claims/{claim_id}/fail", json={"reason": reason})


def status(client: TestClient, claim_id: str) -> str:
    return client.get(f"/api/claims/{claim_id}").json()["status"]


def missed(client: TestClient, run_id: int = 1) -> list[str]:
    response = client.get(f"/api/runs/{run_id}/missed").json()
    return [claim["claim_id"] for claim in response]


def decline(client: TestClient, claim_id: str):
    return client.post(
        f"/api/claims/{claim_id}/decision",
        json={
            "decision": "decline",
            "payout": 0,
            "explanation": "Not covered.",
            "policy_section": "Section 9, General exclusions",
        },
    )


def test_a_run_needs_a_limit_and_runs_one_at_a_time(client: TestClient):
    assert client.get("/api/runs/latest").json() is None
    assert start_run(client, 0).status_code == 422
    run = start_run(client).json()
    assert run["limit"] == 5
    assert run["status"] == "running"
    assert run["todos"] == []
    assert start_run(client).status_code == 409
    finished = client.post(
        "/api/runs/1/finish", json={"summary": "Done.", "status": "finished"}
    ).json()
    assert finished["summary"] == "Done."
    assert finished["finished_at"]
    assert start_run(client, 3).json()["run_id"] == 2
    assert client.get("/api/runs/latest").json()["limit"] == 3


def test_a_finished_run_cannot_be_finished_or_used_again(client: TestClient):
    start_run(client)
    client.post("/api/runs/1/finish", json={"summary": "", "status": "failed"})
    finish = client.post("/api/runs/1/finish", json={"summary": "", "status": "failed"})
    assert finish.status_code == 409
    assert take(client, "CLM-1001").status_code == 409
    assert missed(client) == []


def test_the_to_do_list_is_replaced_in_order(client: TestClient):
    start_run(client)
    first = [
        {"text": "Work CLM-1001", "status": "in_progress"},
        {"text": "Work CLM-1002", "status": "todo"},
    ]
    assert client.put("/api/runs/1/todos", json={"todos": first}).status_code == 200
    second = [
        {"text": "Work CLM-1002", "status": "done"},
        {"text": "Work CLM-1001", "status": "left_for_handler"},
    ]
    client.put("/api/runs/1/todos", json={"todos": second})
    assert client.get("/api/runs/latest").json()["todos"] == second
    bad = [{"text": "Work CLM-1001", "status": "waiting"}]
    assert client.put("/api/runs/1/todos", json={"todos": bad}).status_code == 422
    assert client.put("/api/runs/9/todos", json={"todos": []}).status_code == 404
    assert client.get("/api/runs/latest").json()["todos"] == second


def test_the_cap_counts_different_claims(client: TestClient):
    start_run(client, 2)
    assert take(client, "CLM-1001").status_code == 200
    assert take(client, "CLM-1002").status_code == 200
    over = take(client, "CLM-1003")
    assert over.status_code == 409
    assert "cap of 2" in over.json()["detail"]
    start(client, "CLM-1001")
    fail(client, "CLM-1001")
    assert take(client, "CLM-1001").status_code == 200
    assert take(client, "CLM-9999").status_code == 404


def test_only_a_waiting_claim_can_be_taken(client: TestClient):
    start_run(client)
    start(client, "CLM-1001")
    assert take(client, "CLM-1001").status_code == 409
    decline(client, "CLM-1001")
    assert take(client, "CLM-1001").status_code == 409


def test_missed_claims_are_those_within_the_cap(client: TestClient):
    start_run(client, 5)
    assert missed(client) == [f"CLM-100{n}" for n in range(1, 6)]
    for number in range(1, 6):
        claim_id = f"CLM-100{number}"
        take(client, claim_id)
        start(client, claim_id)
        decline(client, claim_id)
    assert missed(client) == []


def test_a_claim_back_in_the_queue_is_missed_even_when_the_cap_is_used(
    client: TestClient,
):
    start_run(client, 1)
    take(client, "CLM-1001")
    start(client, "CLM-1001")
    assert missed(client) == []
    fail(client, "CLM-1001")
    assert missed(client) == ["CLM-1001"]


def test_a_claim_that_fails_twice_is_left_for_a_handler(client: TestClient):
    start(client, "CLM-1001")
    first = fail(client, "CLM-1001", "The model timed out").json()
    assert first["status"] == "waiting"
    start(client, "CLM-1001")
    second = fail(client, "CLM-1001", "The model timed out again").json()
    assert second["status"] == "needs_handler"
    assert start(client, "CLM-1001").status_code == 409
    assert fail(client, "CLM-1001").status_code == 409
    steps = client.get("/api/claims/CLM-1001/steps").json()
    assert [step["kind"] for step in steps] == ["error", "error"]
    assert (
        steps[0]["text"]
        == "Failed 1 of 2 tries: back in the queue. The model timed out"
    )
    assert steps[1]["text"].startswith("Failed 2 times: left for a handler.")
    start_run(client)
    assert missed(client) == [f"CLM-100{n}" for n in range(2, 7)]


def test_only_an_in_progress_claim_can_fail(client: TestClient):
    assert fail(client, "CLM-1001").status_code == 409
    assert fail(client, "CLM-9999").status_code == 404
    start(client, "CLM-1001")
    decline(client, "CLM-1001")
    assert fail(client, "CLM-1001").status_code == 409
    assert status(client, "CLM-1001") == "decided"


def test_a_decision_and_a_payment_happen_once_even_after_a_failure(
    client: TestClient,
):
    start(client, "CLM-1001")
    approve = {
        "decision": "approve",
        "payout": 200,
        "explanation": "Covered.",
        "policy_section": "Section 3, Trip Delay",
    }
    url = "/api/claims/CLM-1001"
    assert client.post(f"{url}/decision", json=approve).status_code == 200
    assert fail(client, "CLM-1001").status_code == 409
    assert client.post(f"{url}/decision", json=approve).status_code == 409
    assert client.post(f"{url}/payment", json={"amount": 200}).status_code == 200
    assert client.post(f"{url}/payment", json={"amount": 200}).status_code == 409


def test_a_restart_releases_claims_and_closes_runs(client: TestClient, tmp_path: Path):
    start_run(client)
    start(client, "CLM-1001")
    start(client, "CLM-1002")
    fail(client, "CLM-1002")
    start(client, "CLM-1002")
    with TestClient(app) as restarted:
        assert restarted.get("/api/runs/latest").json()["status"] == "failed"
        assert status(restarted, "CLM-1001") == "waiting"
        assert status(restarted, "CLM-1002") == "needs_handler"
    assert (tmp_path / "test.db").exists()


def test_the_queue_shows_the_new_status(client: TestClient):
    start(client, "CLM-1001")
    fail(client, "CLM-1001")
    start(client, "CLM-1001")
    fail(client, "CLM-1001")
    claims = client.get("/api/claims").json()
    assert claims[0]["status"] == "needs_handler"
