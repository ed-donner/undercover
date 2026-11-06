from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def sections_of(document):
    return [
        (section["section"], section["title"])
        for section in client.get("/api/documents/sections").json()
        if section["document"] == document
    ]


def test_the_contents_list_every_section_of_both_documents():
    wording = sections_of("policy_wording")
    manual = sections_of("claims_manual")
    assert [number for number, _ in wording] == list(range(1, 13))
    assert [number for number, _ in manual] == list(range(1, 15))
    assert (10, "How we work out your payment") in wording
    assert (9, "Repeat claims") in manual


def test_read_a_section_in_full():
    meals = client.get("/api/documents/claims_manual/sections/10").json()
    assert meals["title"] == "Meals without receipts"
    assert "flat $35 per traveler" in meals["text"]
    assert "## " not in meals["text"]
    delay = client.get("/api/documents/policy_wording/sections/3").json()
    assert delay["title"] == "Trip Delay"
    assert delay["text"].startswith("We pay when your carrier delays you")


def test_a_section_that_isnt_there():
    missing = client.get("/api/documents/claims_manual/sections/99")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "There is no section 99 in the claims manual."
    assert client.get("/api/documents/handbook/sections/1").status_code == 422


def test_search_finds_what_a_title_hides():
    results = client.get("/api/documents/search", params={"query": "monkey"}).json()
    assert [(r["document"], r["section"]) for r in results] == [("claims_manual", 7)]
    assert results[0]["title"] == "Interpretation notes"
    assert results[0]["lines"][0].startswith("**Wild animals.**")


def test_search_ranks_the_best_section_first():
    results = client.get(
        "/api/documents/search", params={"query": "meals without receipts"}
    ).json()
    assert (results[0]["document"], results[0]["section"]) == ("claims_manual", 10)
    assert len(results) <= 5
    assert all(1 <= len(result["lines"]) <= 2 for result in results)


def test_search_reads_plurals_as_the_word():
    results = client.get("/api/documents/search", params={"query": "animals"}).json()
    assert results[0]["section"] == 7


def test_a_search_that_matches_nothing():
    assert client.get("/api/documents/search", params={"query": "xyzzy"}).json() == []
    assert client.get("/api/documents/search", params={"query": ""}).status_code == 422
