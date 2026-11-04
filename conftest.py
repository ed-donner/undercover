import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.seed import seed


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("UNDERCOVER_DB", str(tmp_path / "test.db"))
    seed()
    return TestClient(app)
