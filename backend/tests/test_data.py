import json
import sqlite3
from pathlib import Path

from backend import db, seed
from backend.reset import reset


def count(table: str) -> int:
    with db.session() as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608


def test_seed_loads_the_business_data(client):
    assert count("claims") == 25
    assert count("policies") == 50
    assert count("customers") == 49
    assert count("handlers") == 3
    assert count("plans") == 3


def test_seed_reads_only_its_named_files(tmp_path, monkeypatch):
    monkeypatch.setenv("UNDERCOVER_DB", str(tmp_path / "test.db"))
    opened: list[str] = []
    read_text = Path.read_text

    def record(self: Path, *args, **kwargs):
        opened.append(self.name)
        return read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", record)
    seed.init_db()
    assert sorted(opened) == sorted(seed.SEED_FILES)
    assert not {"claims_manual.md", "knowledge.json"} & set(opened)
    assert not any(name.startswith(("evals", "security")) for name in seed.SEED_FILES)


def test_init_db_keeps_existing_records(client):
    with db.session() as conn:
        conn.execute("DELETE FROM claims WHERE claim_id = 'CLM-1001'")
    seed.init_db()
    assert count("claims") == 24


def test_reset_restores_the_seed_data(client):
    with db.session() as conn:
        conn.execute("DELETE FROM claims")
    reset()
    assert count("claims") == 25


def test_db_path_defaults_to_the_backend_folder(monkeypatch):
    monkeypatch.delenv("UNDERCOVER_DB", raising=False)
    assert db.db_path() == Path(db.__file__).parent / "undercover.db"


def test_session_closes_the_connection(client):
    with db.session() as conn:
        pass
    try:
        conn.execute("SELECT 1")
    except sqlite3.ProgrammingError:
        return
    raise AssertionError("connection still open")


def test_wording_is_stored_whole(client):
    wording = (seed.DATA / "policy_wording.md").read_text(encoding="utf-8")
    assert client.get("/api/policy-wording").json() == {"text": wording}
    assert json.loads(client.get("/api/claims").text)
