from fastapi.testclient import TestClient

from backend.main import app
from backend.seed import main


def test_seed_reports_what_went_in(capsys):
    main()
    assert capsys.readouterr().out.startswith(
        "Seeded 25 claims, 50 policies, 49 customers and 3 handlers into "
    )


def test_the_backend_seeds_a_missing_database(tmp_path, monkeypatch):
    database = tmp_path / "new.db"
    monkeypatch.setenv("UNDERCOVER_DB", str(database))
    with TestClient(app) as client:
        assert database.exists()
        assert len(client.get("/api/claims").json()) == 25
