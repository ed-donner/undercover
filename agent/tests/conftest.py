import pytest
from fastapi.testclient import TestClient

from agent import common
from backend.main import app
from backend.seed import seed


@pytest.fixture(autouse=True)
def database(tmp_path, monkeypatch):
    """Give each test a freshly seeded database of its own."""
    monkeypatch.setenv("UNDERCOVER_DB", str(tmp_path / "test.db"))
    seed()


@pytest.fixture(autouse=True)
def backend(monkeypatch):
    """Send the agent's calls to the backend in the test, and retry at once."""
    monkeypatch.setattr(common, "backend", lambda: TestClient(app))
    monkeypatch.setattr(common, "RETRY_DELAY_SECONDS", 0)
