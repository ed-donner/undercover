import pytest

from backend import agent_process


def test_run_agent_schedules_the_agent(client, monkeypatch):
    calls = []
    monkeypatch.setattr(agent_process, "start", calls.append)

    response = client.post("/api/claims/CLM-1001/run")

    assert response.status_code == 200
    assert response.json()["status"] == "in progress"
    assert calls == ["CLM-1001"]


def test_a_failed_launch_leaves_the_claim_waiting(client, monkeypatch):
    def fail(claim_id):
        raise OSError("cannot start")

    monkeypatch.setattr(agent_process, "start", fail)

    with pytest.raises(OSError, match="cannot start"):
        client.post("/api/claims/CLM-1001/run")

    assert client.get("/api/claims/CLM-1001").json()["status"] == "waiting"


def test_run_agent_blocked_when_not_waiting(client):
    client.post("/api/claims/CLM-1001/steps", json={"text": "started"})
    response = client.post("/api/claims/CLM-1001/run")
    assert response.status_code == 409


def test_start_launches_the_agent_cli_for_the_claim(monkeypatch):
    launched = []
    monkeypatch.setattr(
        agent_process.subprocess,
        "Popen",
        lambda command, cwd: launched.append((command[1:], cwd)),
    )

    agent_process.start("CLM-1001")

    assert launched == [(["-m", "agent", "--claim", "CLM-1001"], agent_process.ROOT)]
