import pytest
from fastapi.testclient import TestClient

from agent import base
from backend import db
from backend.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(base, "backend", lambda: TestClient(app))
    with TestClient(app) as client:
        yield client
