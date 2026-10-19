import pytest
from fastapi.testclient import TestClient

from backend import runner


@pytest.fixture
def stub_agent(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Replace the agent with one that declines every claim it is given."""
    seen: list[str] = []

    def run(claim_id: str, thread_id: str) -> str:
        seen.append(claim_id)
        if claim_id == "CLM-1003":
            raise RuntimeError("The model is down")
        client.post(f"/api/claims/{claim_id}/start")
        client.post(
            f"/api/claims/{claim_id}/decision",
            json={
                "decision": "decline",
                "payout": 0,
                "explanation": "Not covered.",
                "policy_section": "Section 9, General exclusions",
            },
        )
        return "Declined."

    monkeypatch.setattr(runner, "work", run)
    return seen


def status(client: TestClient, claim_id: str) -> str:
    return client.get(f"/api/claims/{claim_id}").json()["status"]


def test_run_claim(client: TestClient, stub_agent: list[str]):
    response = client.post("/api/claims/CLM-1001/run")
    assert response.status_code == 202
    assert response.json()["status"] == "in_progress"
    assert stub_agent == ["CLM-1001"]
    assert status(client, "CLM-1001") == "decided"


def test_run_claim_needs_a_waiting_claim(client: TestClient, stub_agent: list[str]):
    client.post("/api/claims/CLM-1001/run")
    assert client.post("/api/claims/CLM-1001/run").status_code == 409
    assert client.post("/api/claims/CLM-9999/run").status_code == 404
    assert stub_agent == ["CLM-1001"]


def test_run_queue_works_every_waiting_claim(client: TestClient, stub_agent: list[str]):
    client.post("/api/claims/CLM-1002/run")
    response = client.post("/api/queue/run")
    assert response.status_code == 202
    assert response.json() == {"waiting": 24}
    claims = client.get("/api/claims").json()
    stuck = [claim["claim_id"] for claim in claims if claim["status"] != "decided"]
    assert stuck == ["CLM-1003"]
    assert len(stub_agent) == 25
    assert stub_agent.count("CLM-1002") == 1
