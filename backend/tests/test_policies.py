import pytest
from fastapi.testclient import TestClient

from backend import main
from backend.main import app
from backend.policies import list_policies, read_section, sections


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SHOPPIE_DATABASE_PATH", str(tmp_path / "policies.sqlite3"))
    monkeypatch.setattr(main, "run_in_background", lambda *args: None)
    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.parametrize(
    ("policy", "first", "count"),
    [
        ("shopping", "1. About Shoppie", 12),
        ("cancellation", "1. Scope", 8),
        ("returns", "1. Our commitment", 10),
    ],
)
def test_each_policy_yields_the_headings_in_its_file(policy, first, count):
    titles = [section["title"] for section in sections(policy)]
    assert titles[0] == first
    assert len(titles) == count


def test_a_section_runs_to_the_next_heading_of_its_level():
    delivery = read_section("shopping", "5-delivery-and-shipping")
    perishable = read_section("shopping", "perishable-products")
    assert delivery is not None
    assert perishable is not None
    assert "### Perishable products" in delivery["content"]
    assert "### Non-perishable products" in delivery["content"]
    assert "## 6." not in delivery["content"]
    assert "### Non-perishable products" not in perishable["content"]


def test_unknown_policies_and_sections_are_not_found():
    assert read_section("warranty", "1-scope") is None
    assert read_section("cancellation", "99-missing") is None


def test_policy_list_names_every_policy_and_section(client):
    policies = client.get("/api/policies").json()
    assert [policy["policy"] for policy in policies] == [
        "shopping",
        "cancellation",
        "returns",
    ]
    assert policies[1]["name"] == "Shoppie Cancellation Policy"
    assert {
        "id": "2-customer-requested-cancellations",
        "title": "2. Customer-requested cancellations",
    } in policies[1]["sections"]
    assert policies == list_policies()


def test_reading_a_section_records_it_on_the_request(client):
    client.post("/api/requests/REQ-7001/start")
    url = (
        "/api/requests/REQ-7001/policies/cancellation/sections/"
        "2-customer-requested-cancellations"
    )
    section = client.get(url).json()
    missing = client.get(
        "/api/requests/REQ-7001/policies/cancellation/sections/99-missing"
    )
    steps = client.get("/api/requests/REQ-7001").json()["steps"]

    assert section["title"] == "2. Customer-requested cancellations"
    assert "at no charge" in section["content"]
    assert missing.status_code == 404
    assert steps[-1] == {
        **steps[-1],
        "stage": "read_section",
        "message": (
            "Read Shoppie Cancellation Policy, 2. Customer-requested cancellations."
        ),
    }


def test_reading_a_section_needs_a_request_in_progress(client):
    response = client.get(
        "/api/requests/REQ-7001/policies/cancellation/sections/1-scope"
    )
    steps = client.get("/api/requests/REQ-7001").json()["steps"]
    assert response.status_code == 409
    assert steps == []


def test_context_holds_no_policy_text(client):
    context = client.get("/api/requests/REQ-7001/context").json()
    assert "policy" not in context
    assert context["request"]["request_id"] == "REQ-7001"
    assert set(context["customer"]) == {"customer_id", "name"}
    assert "reason_code" not in context["request"]
    assert "required_action" not in context["request"]
    assert "shipping_address_id" not in context["order"]
    assert client.get("/api/requests/REQ-0000/context").status_code == 404
