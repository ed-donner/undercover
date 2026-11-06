import threading

from backend import db


def test_concurrent_startup_does_not_race_the_schema():
    """Regression test: concurrent requests at startup once raced to 'no such table'."""
    db._state["connection"] = None  # simulate a fresh, unseeded backend process

    errors: list[Exception] = []

    def query() -> None:
        try:
            db.get_connection().execute("SELECT 1 FROM claims LIMIT 1").fetchone()
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=query) for _ in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []


def test_concurrent_reads_on_the_shared_connection_do_not_race():
    """Regression test: concurrent reads once hit 'bad parameter or API misuse'."""
    db.reset_database()

    errors: list[Exception] = []

    def read() -> None:
        try:
            db.fetch_claims()
            db.fetch_claim("CLM-1001")
            db.fetch_handlers()
            db.fetch_events("CLM-1001")
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=read) for _ in range(30)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
