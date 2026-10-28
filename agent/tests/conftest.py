import pytest
from fastapi.testclient import TestClient

from agent import main
from backend.main import app


@pytest.fixture(autouse=True)
def fresh_backend(tmp_path, monkeypatch):
    monkeypatch.setenv("UNDERCOVER_DB", str(tmp_path / "test.db"))
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
