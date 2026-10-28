import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setenv("UNDERCOVER_DB", str(tmp_path / "test.db"))


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client
