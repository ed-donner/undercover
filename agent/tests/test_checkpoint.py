from concurrent.futures import ThreadPoolExecutor

from agent import checkpoint


class FakePool:
    """Counts the pools opened, and hands out connections that do nothing."""

    opened = 0

    def __init__(self, *args, **kwargs):
        FakePool.opened += 1

    def open(self):
        pass

    def connection(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, *args):
        pass


class FakeSaver:
    def __init__(self, pool):
        pass

    def setup(self):
        pass


def test_racing_threads_open_one_pool(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host/db")
    monkeypatch.setattr(checkpoint, "ConnectionPool", FakePool)
    monkeypatch.setattr(checkpoint, "PostgresSaver", FakeSaver)
    checkpoint.forget()

    with ThreadPoolExecutor(8) as threads:
        savers = list(threads.map(lambda _: checkpoint.saver(), range(8)))

    assert FakePool.opened == 1
    assert len({id(saver) for saver in savers}) == 1
    checkpoint.forget()
