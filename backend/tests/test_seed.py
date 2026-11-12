from backend import db, seed


def test_reset_puts_every_claim_back_to_waiting(client):
    client.post("/api/claims/CLM-1001/steps", json={"text": "started"})
    assert client.get("/api/claims/CLM-1001").json()["status"] == "in progress"

    seed.reset()

    statuses = {c["status"] for c in client.get("/api/claims").json()}
    assert statuses == {"waiting"}
    assert client.get("/api/claims/CLM-1001/steps").json() == []


def test_database_url_uses_the_postgres_driver(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host:5432/postgres")
    assert db.database_url() == "postgresql+psycopg://u:p@host:5432/postgres"
