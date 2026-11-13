from pathlib import Path

import pytest

from backend.documents import Documents, seed_documents
from backend.store import Store
from backend.tests.helpers import start
from backend.workflow import Workflow


def read(client, run, document_id="manual", section=9, claim_id="CLM-1001"):
    return client.post(
        f"/api/claims/{claim_id}/reads",
        json={"run_id": run, "document_id": document_id, "section": section},
    )


def test_catalog_and_complete_sections(client):
    catalog = client.get("/api/documents").json()
    assert len(catalog) == 26
    assert {s["version"] for s in catalog if s["document_id"] == "manual"} == {"2026.2"}
    assert all("text" not in item for item in catalog)
    section = client.get("/api/documents/manual/sections/5").json()
    assert "| Benefit | Required documents |" in section["text"]
    assert "30 days" in section["text"]
    assert "## 6." not in section["text"]
    assert section["title"] == "Documents and document requests"
    assert client.get("/api/documents/other/sections/1").status_code == 404
    assert client.get("/api/documents/manual/sections/99").status_code == 404
    assert client.get("/api/documents/manual/sections/0").status_code == 404


@pytest.mark.parametrize(
    ("query", "number"),
    [("repeat", 9), ("wild animals", 7), ("meals without receipts", 10)],
)
def test_keyword_search(client, query, number):
    matches = client.post(
        "/api/documents/search", json={"document_id": "manual", "query": query}
    ).json()
    assert number in {section["section"] for section in matches}
    assert all("text" not in hit and len(hit["excerpt"]) <= 240 for hit in matches)
    assert client.get("/api/claims/CLM-1001/reads").json() == []


def test_no_matches_or_arbitrary_file_access(client):
    for query in ("", "nonexistentkeyword"):
        assert (
            client.post(
                "/api/documents/search", json={"document_id": "manual", "query": query}
            ).json()
            == []
        )
    for document_id in (
        "../../.env",
        "data/evals/",
        "https://example.com",
        "claims.json",
    ):
        assert (
            client.post(
                "/api/documents/search",
                json={"document_id": document_id, "query": "claim"},
            ).status_code
            == 404
        )


def test_reads_are_audited_and_attempt_scoped(client):
    run = start(client).json()["run_id"]
    assert read(client, run).status_code == 200
    assert read(client, run, claim_id="CLM-1002").status_code == 409
    assert read(client, "no").status_code == 404
    assert read(client, run, section=100).status_code == 404
    records = client.get("/api/claims/CLM-1001/reads").json()
    assert len(records) == 1
    assert records[0]["run_id"] == run
    assert "third claim" in records[0]["text"]
    assert records[0]["version"] == "2026.2"
    assert records[0]["read_at"]
    assert client.get("/api/claims/CLM-1002/reads").json() == []
    assert "section 9" in client.get("/api/claims/CLM-1001/events").json()[-1]["label"]
    Workflow(client.app.state.store).finish(run, "Synthetic failure")
    assert read(client, run).status_code == 409


def test_new_decisions_require_read_references(client):
    run = start(client).json()["run_id"]
    payload = {
        "run_id": run,
        "outcome": "decline",
        "payout": 0,
        "calculation": "No payment.",
        "explanation": "Synthetic coverage fixture. The rule excludes it.",
        "policy_sections": [3],
        "manual_version": "2026.2",
        "manual_sections": [9],
    }
    path = "/api/claims/CLM-1001/decision"
    assert client.post(path, json=payload).status_code == 409
    read(client, run, "manual", 9)
    assert client.post(path, json=payload).status_code == 409
    read(client, run, "wording", 3)
    assert (
        client.post(path, json={**payload, "manual_sections": [8]}).status_code == 409
    )
    assert (
        client.post(path, json={**payload, "manual_version": "wrong"}).status_code
        == 409
    )
    assert (
        client.post(path, json={**payload, "manual_version": None}).status_code == 409
    )
    assert client.post(path, json={**payload, "manual_sections": []}).status_code == 422
    assert client.post(path, json=payload).status_code == 200
    decision = client.get("/api/claims/CLM-1001").json()["decision"]
    assert decision["manual_sections"] == [9]
    assert decision["manual_version"] == "2026.2"


def test_existing_decisions_have_no_invented_provenance(client):
    run = start(client).json()["run_id"]
    store = client.app.state.store
    with store.transaction() as connection:
        connection.execute(
            "INSERT INTO decisions (claim_id, run_id, outcome, payout_cents, "
            "calculation, explanation, policy_sections, recorded_at) "
            "VALUES (?, ?, 'decline', 0, 'Original calculation', "
            "'Original reason', '[3]', '2026-01-01')",
            ("CLM-1001", run),
        )
    store.initialize()
    decision = Workflow(store).detail("CLM-1001").decision
    assert decision
    assert decision.manual_version is None
    assert decision.manual_sections == []
    assert decision.explanation == "Original reason"


def test_backfill_existing_database_without_reseeding(tmp_path, monkeypatch):
    store = Store(tmp_path / "backfill.db")
    store.initialize()
    with store.transaction() as connection:
        connection.execute("DELETE FROM document_sections")
        connection.execute("UPDATE claims SET status = 'decided' WHERE id = 'CLM-1001'")
    opened = []
    original = Path.read_text

    def track(path, *args, **kwargs):
        opened.append(path.name)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", track)
    store.initialize()
    assert opened == ["policy_wording.md", "claims_manual.md"]
    assert store.claim("CLM-1001")["status"] == "decided"
    assert len(Documents(store).catalog()) == 26


def test_unversioned_document_is_rejected(tmp_path):
    (tmp_path / "policy_wording.md").write_text("## 1. No version")
    store = Store(tmp_path / "bad.db")
    store.initialize()
    with store.transaction() as connection:
        connection.execute("DELETE FROM document_sections")
        with pytest.raises(ValueError, match="version"):
            seed_documents(connection, tmp_path)
