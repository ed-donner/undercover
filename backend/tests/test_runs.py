import pytest

from backend import main


def decline(claim_id, thread_id):
    main.record_decision(
        claim_id,
        main.Decision(
            decision="decline",
            payout=0,
            reason="Not covered.",
            policy_section="Section 9",
        ),
    )


@pytest.fixture
def runs(monkeypatch):
    seen = []

    def fake_run(claim_id, thread_id):
        seen.append((claim_id, thread_id))
        decline(claim_id, thread_id)

    monkeypatch.setattr(main.agent, "run", fake_run)
    return seen


def test_run_agent_decides_a_waiting_claim(client, runs):
    client.post(
        "/api/claims/CLM-1001/steps", json={"kind": "reply", "text": "Old run."}
    )
    assert client.post("/api/claims/CLM-1001/run").json() == {"status": "in_progress"}
    assert runs[0][0] == "CLM-1001"
    assert runs[0][1].startswith("CLM-1001-")
    assert client.get("/api/claims/CLM-1001").json()["status"] == "decided"
    assert client.get("/api/claims/CLM-1001/steps").json() == []


def test_run_agent_needs_a_waiting_claim(client, runs):
    client.post("/api/claims/CLM-1001/run")
    response = client.post("/api/claims/CLM-1001/run")
    assert response.status_code == 409
    assert len(runs) == 1


def test_run_agent_on_an_unknown_claim_is_404(client, runs):
    assert client.post("/api/claims/CLM-0000/run").status_code == 404


def test_run_queue_runs_only_waiting_claims(client, runs):
    client.post("/api/claims/CLM-1001/run")
    assert client.post("/api/queue/run").json() == {"waiting": 24}
    assert len(runs) == 25
    statuses = {c["status"] for c in client.get("/api/claims").json()}
    assert statuses == {"decided"}


def test_a_run_without_a_decision_puts_the_claim_back(client, monkeypatch):
    monkeypatch.setattr(main.agent, "run", lambda claim_id, thread_id: "Hello.")
    client.post("/api/claims/CLM-1001/run")
    assert client.get("/api/claims/CLM-1001").json()["status"] == "waiting"
    step = client.get("/api/claims/CLM-1001/steps").json()[-1]
    assert step["kind"] == "error"
    assert step["text"].startswith("The agent finished without recording a decision.")
