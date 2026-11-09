from backend import claims

CLAIM = "/api/claims/CLM-1001"


def acquire(client, owner):
    return client.post(f"{CLAIM}/lease", json={"owner": owner})


def release(client, owner):
    return client.post(f"{CLAIM}/lease/release", json={"owner": owner})


def test_a_second_agent_is_refused_while_the_lease_is_held(client):
    assert acquire(client, "a").json() == {"lease_seconds": claims.LEASE_SECONDS}

    assert acquire(client, "b").status_code == 409


def test_the_holder_renews_its_own_lease(client):
    acquire(client, "a")

    assert acquire(client, "a").status_code == 200


def test_an_expired_lease_can_be_taken(client, monkeypatch):
    monkeypatch.setattr(claims, "LEASE_SECONDS", -1)
    acquire(client, "a")

    assert acquire(client, "b").status_code == 200


def test_a_released_lease_can_be_taken(client):
    acquire(client, "a")

    release(client, "a")

    assert acquire(client, "b").status_code == 200


def test_only_the_holder_can_release(client):
    acquire(client, "a")

    release(client, "b")

    assert acquire(client, "b").status_code == 409


def test_a_leased_claim_is_not_unfinished_until_the_lease_ends(client):
    client.post(f"{CLAIM}/steps", json={"text": "started"})
    assert client.get("/api/unfinished-claims").json() == ["CLM-1001"]

    acquire(client, "a")
    assert client.get("/api/unfinished-claims").json() == []

    release(client, "a")
    assert client.get("/api/unfinished-claims").json() == ["CLM-1001"]


def test_an_unknown_claim_has_no_lease(client):
    assert (
        client.post("/api/claims/CLM-0/lease", json={"owner": "a"}).status_code == 404
    )
