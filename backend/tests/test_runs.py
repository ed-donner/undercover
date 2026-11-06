from fastapi.testclient import TestClient

from backend.main import app
from backend.seed import seed

client = TestClient(app)
TODOS = [
    {"content": "Work CLM-1001", "status": "done"},
    {"content": "Work CLM-1002", "status": "in_progress"},
    {"content": "Work CLM-1003", "status": "to_do"},
    {"content": "Work CLM-1004", "status": "left_for_handler"},
]


def test_there_is_no_run_before_the_first():
    assert client.get("/api/runs/latest").json() is None


def test_a_run_starts_with_an_empty_to_do_list():
    run = client.post("/api/runs").json()
    assert run["run_id"] == 1
    assert run["todos"] == []
    assert run["started_at"]
    assert (run["summary"], run["finished_at"]) == (None, None)


def test_the_to_do_list_is_replaced_and_shown_with_the_latest_run():
    client.post("/api/runs")
    client.put("/api/runs/1/todos", json={"todos": TODOS[:1]})
    assert client.put("/api/runs/1/todos", json={"todos": TODOS}).json()["todos"] == (
        TODOS
    )
    assert client.get("/api/runs/latest").json()["todos"] == TODOS


def test_a_to_do_item_has_one_of_four_statuses():
    client.post("/api/runs")
    item = {"content": "Work CLM-1001", "status": "pending"}
    assert client.put("/api/runs/1/todos", json={"todos": [item]}).status_code == 422


def test_a_finished_run_keeps_its_summary_and_its_list():
    client.post("/api/runs")
    finished = client.post("/api/runs/1/finish", json={"summary": "Worked 5 claims."})
    assert finished.json()["summary"] == "Worked 5 claims."
    assert finished.json()["finished_at"]
    again = client.post("/api/runs/1/finish", json={"summary": "Again."})
    assert again.status_code == 409
    assert again.json()["detail"] == "Run 1 has finished."
    assert client.put("/api/runs/1/todos", json={"todos": TODOS}).status_code == 409
    assert client.get("/api/runs/latest").json()["summary"] == "Worked 5 claims."


def test_the_latest_run_is_the_newest():
    client.post("/api/runs")
    client.post("/api/runs")
    assert client.get("/api/runs/latest").json()["run_id"] == 2


def test_an_unknown_run():
    assert client.put("/api/runs/9/todos", json={"todos": []}).status_code == 404
    assert client.post("/api/runs/9/finish", json={"summary": "x"}).status_code == 404


def test_a_reseed_clears_the_runs():
    client.post("/api/runs")
    seed()
    assert client.get("/api/runs/latest").json() is None
    assert client.post("/api/runs").json()["run_id"] == 1
