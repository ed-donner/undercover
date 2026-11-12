import pytest


@pytest.fixture(autouse=True)
def no_outside_services(monkeypatch):
    """Tests run on SQLite and make no network calls, whatever .env holds."""
    for name in ("DATABASE_URL", "LANGFUSE_SECRET_KEY", "LANGFUSE_PUBLIC_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("UNDERCOVER_AGENT", "http://127.0.0.1:9")
