from contextlib import nullcontext

import pytest
from fastapi.testclient import TestClient

from agent import main
from backend.main import app
from backend.store import Store


@pytest.fixture
def api(tmp_path, monkeypatch):
    """Run the backend on a fresh database and point the agent at it."""
    monkeypatch.setenv("SHOPPIE_DATABASE_PATH", str(tmp_path / "agent.sqlite3"))
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    with TestClient(app) as client:
        monkeypatch.setattr(main, "backend", lambda: nullcontext(client))
        yield client


@pytest.fixture
def store(api) -> Store:
    """Return the store behind the test backend."""
    return app.state.store
