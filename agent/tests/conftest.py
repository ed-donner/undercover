import pytest

from backend.tests.fixtures import make_client


@pytest.fixture
def client(tmp_path, monkeypatch):
    yield from make_client(tmp_path, monkeypatch)
