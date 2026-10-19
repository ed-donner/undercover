import re
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi.testclient import TestClient

from backend.db import DATA, connect, init_db

ROOT = Path(__file__).parent.parent.parent


def test_seeds_the_queue(client: TestClient):
    claims = client.get("/api/claims").json()
    assert len(claims) == 25
    assert {claim["status"] for claim in claims} == {"waiting"}
    first = claims[0]
    assert first["claim_id"] == "CLM-1001"
    assert first["customer_name"] == "Maya Patel"
    assert first["decision"] is None
    assert first["payout"] is None


def test_seeding_runs_once(client: TestClient, tmp_path: Path):
    init_db()
    with sqlite3.connect(tmp_path / "test.db") as conn:
        counts = [
            conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608
            for table in ("claims", "policies", "customers", "handlers", "decisions")
        ]
    assert counts == [25, 50, 49, 3, 0]


def test_get_claim(client: TestClient):
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["story"].startswith("My flight home from Rome")
    assert len(claim["items"]) == 3
    assert len(claim["documents"]) == 4
    assert claim["customer_name"] == "Maya Patel"
    assert claim["decision"] is None
    assert claim["payment"] is None
    assert claim["sign_off"] is None


def test_unknown_things_are_404(client: TestClient):
    for path in ("claims/CLM-9999", "policies/POL-9", "customers/CUS-9"):
        assert client.get(f"/api/{path}").status_code == 404


def test_get_policy(client: TestClient):
    policy = client.get("/api/policies/POL-2001").json()
    assert policy["plan"] == "premium"
    assert policy["trip"]["destination"] == "Rome, Italy"
    assert policy["travelers"] == ["Maya Patel"]
    assert policy["add_ons"] == []


def test_get_customer_leaves_out_contact_details(client: TestClient):
    customer = client.get("/api/customers/CUS-3001").json()
    assert customer["name"] == "Maya Patel"
    assert customer["previous_claims"][0]["claim_id"] == "CLM-0412"
    assert not {"email", "phone", "address", "date_of_birth"} & customer.keys()


def test_wording_and_instructions(client: TestClient):
    wording = client.get("/api/policy-wording").json()["text"]
    assert wording == (DATA / "policy_wording.md").read_text(encoding="utf-8")
    instructions = client.get("/api/instructions").json()
    for agent in ("queue", "claim"):
        assert instructions[agent] == (
            ROOT / "backend" / "instructions" / f"{agent}.md"
        ).read_text(encoding="utf-8")


def test_sections_of_the_documents(client: TestClient):
    wording = client.get("/api/documents/wording/sections").json()
    assert [section["number"] for section in wording] == list(range(13))
    assert wording[10] == {"number": 10, "title": "How we work out your payment"}
    manual = client.get("/api/documents/manual/sections").json()
    assert [section["number"] for section in manual] == list(range(15))
    assert manual[9]["title"] == "Repeat claims"


def test_read_a_section(client: TestClient):
    text = client.get("/api/documents/manual/sections/9").json()["text"]
    assert text.startswith("## 9. Repeat claims")
    assert "third claim within any 12 month period" in text
    assert "## 10." not in text
    wording = client.get("/api/documents/wording/sections/10").json()["text"]
    assert wording.startswith("## 10. How we work out your payment")


def test_no_text_is_lost_between_sections(client: TestClient):
    for document, name in (("wording", "policy_wording"), ("manual", "claims_manual")):
        whole = (DATA / f"{name}.md").read_text(encoding="utf-8")
        numbers = [
            section["number"]
            for section in client.get(f"/api/documents/{document}/sections").json()
        ]
        parts = [
            client.get(f"/api/documents/{document}/sections/{number}").json()["text"]
            for number in numbers
        ]
        assert "\n\n".join(parts) == whole.strip()


def test_unknown_documents_and_sections_are_404(client: TestClient):
    assert client.get("/api/documents/evidence/sections").status_code == 404
    assert client.get("/api/documents/manual/sections/99").status_code == 404


def test_list_handlers(client: TestClient):
    handlers = client.get("/api/handlers").json()
    assert [handler["handler_id"] for handler in handlers] == [
        "HND-01",
        "HND-02",
        "HND-03",
    ]
    assert "email" not in handlers[0]


def test_every_operation_is_documented(client: TestClient):
    paths = client.get("/openapi.json").json()["paths"]
    for path, methods in paths.items():
        for method, operation in methods.items():
            where = f"{method} {path}"
            assert operation.get("operationId"), where
            assert operation.get("description"), where
            assert "\n" not in operation["description"].strip(), where
            for parameter in operation.get("parameters", []):
                assert parameter["required"], where


def test_the_answer_key_is_out_of_reach(client: TestClient):
    pattern = re.compile("eval" + "s")
    for folder in ("backend", "agent"):
        for source in (ROOT / folder).rglob("*.py"):
            if "tests" not in source.parts:
                assert not pattern.search(source.read_text(encoding="utf-8")), source
    assert client.get("/api/claims/CLM-1001").json()["decision"] is None


def test_a_connection_works_across_the_threads_a_request_uses(client: TestClient):
    db = connect()
    query = "SELECT COUNT(*) FROM claims"
    with ThreadPoolExecutor() as pool:
        count = pool.submit(lambda: db.execute(query).fetchone()[0]).result()
        pool.submit(db.close).result()
    assert count == 25


def test_the_claim_instructions_cover_the_essentials(client: TestClient):
    text = client.get("/api/instructions").json()["claim"]
    assert len(text.splitlines()) <= 60
    for needed in (
        "$1,000.00",
        "approve",
        "decline",
        "refer",
        "list_sections",
        "read_section",
        "two or three sentences",
        "eligible amount",
    ):
        assert needed in text


def test_the_queue_instructions_cover_the_essentials(client: TestClient):
    text = client.get("/api/instructions").json()["queue"]
    assert len(text.splitlines()) <= 60
    for needed in ("write_todos", "work_claim", "check_queue", "summary"):
        assert needed in text
