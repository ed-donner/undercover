import pytest
from fastapi.testclient import TestClient

from backend import runner


@pytest.fixture
def stub_agent(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Replace the claim agent with one that declines every claim it is given."""
    seen: list[str] = []

    def work(claim_id: str, thread_id: str) -> str:
        seen.append(claim_id)
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

    monkeypatch.setattr(runner, "work", work)
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
