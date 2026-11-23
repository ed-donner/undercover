import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A client for the backend, on a fresh database seeded from data/."""
    monkeypatch.setenv("UNDERCOVER_DB", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        yield client
