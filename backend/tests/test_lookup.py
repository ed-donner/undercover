def test_sections_are_listed(client):
    manual = client.get("/api/sections/manual").json()
    wording = client.get("/api/sections/wording").json()
    assert len(manual) == 14
    assert len(wording) == 12
    assert manual[6] == {"number": 7, "title": "Interpretation notes"}
    assert "text" not in manual[0]


def test_search_finds_the_right_section(client):
    found = client.get(
        "/api/sections/manual/search", params={"query": "wild animals"}
    ).json()
    assert found[0]["number"] == 7
    assert "wild animal" in found[0]["snippet"].lower()
    assert len(found) <= 5


def test_search_with_no_match_is_empty(client):
    assert (
        client.get("/api/sections/wording/search", params={"query": "zzzz"}).json()
        == []
    )


def test_read_returns_only_that_section_and_records_it(client):
    section = client.post(
        "/api/claims/CLM-1001/reads", json={"document": "manual", "number": 10}
    ).json()
    assert section["title"] == "Meals without receipts"
    assert "Wild animals" not in section["text"]
    client.post("/api/claims/CLM-1001/reads", json={"document": "manual", "number": 10})
    client.post("/api/claims/CLM-1001/reads", json={"document": "wording", "number": 3})
    reads = client.get("/api/claims/CLM-1001").json()["reads"]
    assert reads == [
        {"document": "manual", "number": 10, "title": "Meals without receipts"},
        {"document": "wording", "number": 3, "title": "Trip Delay"},
    ]


def test_read_unknown_section_is_404(client):
    body = {"document": "manual", "number": 99}
    assert client.post("/api/claims/CLM-1001/reads", json=body).status_code == 404
    assert (
        client.post("/api/claims/NOPE/reads", json={**body, "number": 1}).status_code
        == 404
    )
