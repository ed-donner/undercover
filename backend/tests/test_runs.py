DECISION = {
    "decision": "decline",
    "payout": 0,
    "section": "9",
    "reason": "Outside trip.",
}


def new_run(client, cap):
    return client.post("/api/runs", json={"cap": cap}).json()["run_id"]


def start(client, run_id, claim_id):
    return client.post(f"/api/runs/{run_id}/claims/{claim_id}/start")


def status(client, claim_id):
    return client.get(f"/api/claims/{claim_id}").json()["status"]


def test_todo_list_is_stored_and_replaced(client):
    assert client.get("/api/runs/current").json() is None
    run_id = new_run(client, 2)
    items = [
        {"text": "Work CLM-1001", "state": "todo", "claim_id": "CLM-1001"},
        {"text": "Work CLM-1002", "state": "in_progress", "claim_id": "CLM-1002"},
    ]
    client.put(f"/api/runs/{run_id}/todos", json={"items": items})
    run = client.get("/api/runs/current").json()
    assert [t["state"] for t in run["todos"]] == ["todo", "in_progress"]
    client.put(f"/api/runs/{run_id}/todos", json={"items": items[:1]})
    assert len(client.get("/api/runs/current").json()["todos"]) == 1


def test_bad_todo_state_is_rejected(client):
    run_id = new_run(client, 2)
    item = {"text": "x", "state": "nearly", "claim_id": ""}
    assert (
        client.put(f"/api/runs/{run_id}/todos", json={"items": [item]}).status_code
        == 422
    )


def test_backend_ticks_the_todo_as_the_claim_moves(client):
    run_id = new_run(client, 2)
    item = {"text": "Work CLM-1001", "state": "todo", "claim_id": "CLM-1001"}
    client.put(f"/api/runs/{run_id}/todos", json={"items": [item]})
    start(client, run_id, "CLM-1001")
    assert client.get("/api/runs/current").json()["todos"][0]["state"] == "in_progress"
    client.post("/api/claims/CLM-1001/decision", json=DECISION)
    assert client.get("/api/runs/current").json()["todos"][0]["state"] == "done"


def test_cap_blocks_the_next_new_claim(client):
    run_id = new_run(client, 2)
    assert start(client, run_id, "CLM-1001").status_code == 200
    assert start(client, run_id, "CLM-1002").status_code == 200
    assert start(client, run_id, "CLM-1003").status_code == 409
    assert status(client, "CLM-1003") == "waiting"
    assert client.get(f"/api/runs/{run_id}/waiting").json()["worked"] == [
        "CLM-1001",
        "CLM-1002",
    ]


def test_cap_must_be_positive(client):
    assert client.post("/api/runs", json={"cap": 0}).status_code == 422


def test_a_claim_in_progress_cannot_be_started_again(client):
    run_id = new_run(client, 2)
    start(client, run_id, "CLM-1001")
    assert start(client, run_id, "CLM-1001").status_code == 409


def test_first_failure_requeues_and_second_leaves_for_a_handler(client):
    run_id = new_run(client, 1)
    start(client, run_id, "CLM-1001")
    item = {"text": "w", "state": "in_progress", "claim_id": "CLM-1001"}
    client.put(f"/api/runs/{run_id}/todos", json={"items": [item]})
    failure = client.post("/api/claims/CLM-1001/failure", json={"reason": "timeout"})
    assert failure.json() == {"status": "waiting"}
    assert client.get("/api/runs/current").json()["todos"][0]["state"] == "todo"
    assert start(client, run_id, "CLM-1001").json() == {"attempt": 2}
    failure = client.post("/api/claims/CLM-1001/failure", json={"reason": "timeout"})
    assert failure.json() == {"status": "left_for_handler"}
    assert (
        client.get("/api/runs/current").json()["todos"][0]["state"]
        == "left_for_handler"
    )
    assert start(client, run_id, "CLM-1001").status_code == 409
    steps = client.get("/api/claims/CLM-1001").json()["steps"]
    assert [s["tool"] for s in steps] == ["failure", "failure"]


def test_a_decided_claim_is_never_requeued(client):
    run_id = new_run(client, 1)
    start(client, run_id, "CLM-1001")
    client.post("/api/claims/CLM-1001/decision", json=DECISION)
    failure = client.post("/api/claims/CLM-1001/failure", json={"reason": "late"})
    assert failure.json() == {"status": "decided"}


def test_a_new_run_and_a_finished_run_sweep_stuck_claims(client):
    run_id = new_run(client, 2)
    start(client, run_id, "CLM-1001")
    new_run(client, 2)
    assert status(client, "CLM-1001") == "waiting"
    run_id = new_run(client, 2)
    start(client, run_id, "CLM-1001")
    client.post(f"/api/runs/{run_id}/finish", json={"summary": "done"})
    assert status(client, "CLM-1001") == "left_for_handler"
    run = client.get("/api/runs/current").json()
    assert run["status"] == "finished"
    assert run["summary"] == "done"
    assert start(client, run_id, "CLM-1002").status_code == 409


def test_missed_claims_within_the_cap(client):
    run_id = new_run(client, 2)
    assert client.get(f"/api/runs/{run_id}/missed").json()["missed"] == [
        "CLM-1001",
        "CLM-1002",
    ]
    start(client, run_id, "CLM-1001")
    client.post("/api/claims/CLM-1001/decision", json=DECISION)
    assert client.get(f"/api/runs/{run_id}/missed").json()["missed"] == ["CLM-1002"]
    start(client, run_id, "CLM-1002")
    client.post("/api/claims/CLM-1002/failure", json={"reason": "x"})
    assert client.get(f"/api/runs/{run_id}/missed").json()["missed"] == ["CLM-1002"]
    start(client, run_id, "CLM-1002")
    client.post("/api/claims/CLM-1002/decision", json=DECISION)
    assert client.get(f"/api/runs/{run_id}/missed").json()["missed"] == []


def test_a_run_on_one_named_claim(client):
    run_id = client.post("/api/runs/claim", json={"claim_id": "CLM-1005"}).json()[
        "run_id"
    ]
    waiting = client.get(f"/api/runs/{run_id}/waiting").json()
    assert [c["claim_id"] for c in waiting["waiting"]] == ["CLM-1005"]
    assert start(client, run_id, "CLM-1001").status_code == 409
    assert start(client, run_id, "CLM-1005").status_code == 200
    assert client.post("/api/runs/claim", json={"claim_id": "NOPE"}).status_code == 404


def test_unknown_run_is_404(client):
    assert client.get("/api/runs/99/waiting").status_code == 404
