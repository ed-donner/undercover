import pytest


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    """Keep agent tests off the real claim database."""
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
