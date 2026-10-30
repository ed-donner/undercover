from agent import agents


def test_run_agent_schedules_the_agent(client, monkeypatch):
    calls = []
    monkeypatch.setattr(agents, "decide_claim", calls.append)

    response = client.post("/api/claims/CLM-1001/run")

    assert response.status_code == 200
    assert response.json()["status"] == "in progress"
    assert calls == ["CLM-1001"]


def test_run_agent_blocked_when_not_waiting(client):
    client.post("/api/claims/CLM-1001/steps", json={"text": "started"})
    response = client.post("/api/claims/CLM-1001/run")
    assert response.status_code == 409
