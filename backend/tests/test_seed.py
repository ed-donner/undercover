import runpy

from backend.store import Store


def test_seed_resets_the_database(tmp_path, monkeypatch, capsys):
    path = tmp_path / "reset.db"
    monkeypatch.setenv("DATABASE_PATH", str(path))
    store = Store(path)
    store.initialize()
    with store.transaction() as connection:
        connection.execute("UPDATE claims SET status = 'decided'")
    runpy.run_module("backend.seed", run_name="__main__")
    statuses = {row["status"] for row in store.queue()}
    assert statuses == {"waiting"}
    assert len(store.queue()) == 25
    assert capsys.readouterr().out == f"Reset {path} with 25 waiting claims.\n"
