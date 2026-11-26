import pytest


@pytest.fixture(autouse=True)
def fresh_database(tmp_path, monkeypatch):
    """Give every test its own database, seeded from data/."""
    monkeypatch.setenv("UNDERCOVER_DB", str(tmp_path / "test.db"))
