import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture(autouse=True)
def backend_in_process(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> TestClient:
    """Point the agent at the in-process backend, which is seeded and uses a temp DB."""
    monkeypatch.setattr("agent.client.backend", lambda: TestClient(app))
    return client
