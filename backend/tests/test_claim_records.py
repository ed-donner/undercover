import json
from pathlib import Path

from backend import money

DATA = Path(__file__).resolve().parents[2] / "data"
FILE_CLAIMS = json.loads((DATA / "claims.json").read_text())
TEXT_FIELDS = [
    "claim_id",
    "policy_id",
    "customer_id",
    "claim_type",
    "submitted_on",
    "incident_date",
    "incident_location",
    "summary",
    "story",
    "documents",
]


def dollars(amount):
    return str(money.dollars(amount))


def test_every_claim_is_as_it_is_in_the_file(client):
    for expected in FILE_CLAIMS:
        claim = client.get(f"/api/claims/{expected['claim_id']}").json()

        for field in TEXT_FIELDS:
            assert claim[field] == expected[field]
        assert claim["amount_claimed"] == dollars(expected["amount_claimed"])
        assert [
            (i["description"], i["category"], i["amount"]) for i in claim["items"]
        ] == [
            (i["description"], i["category"], dollars(i["amount"]))
            for i in expected["items"]
        ]
        assert claim["status"] == "waiting"


def test_the_queue_lists_the_claims_oldest_first(client):
    summaries = client.get("/api/claims").json()

    in_order = sorted(FILE_CLAIMS, key=lambda c: (c["submitted_on"], c["claim_id"]))
    assert [s["claim_id"] for s in summaries] == [c["claim_id"] for c in in_order]
    assert summaries[0]["amount_claimed"] == dollars(in_order[0]["amount_claimed"])
    assert set(summaries[0]) == {
        "claim_id",
        "claim_type",
        "summary",
        "amount_claimed",
        "status",
    }
