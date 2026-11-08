def test_start_run_creates_items_to_do(client):
    response = client.post("/api/runs", json={"claim_ids": ["CLM-1001", "CLM-1002"]})
    assert response.status_code == 200
    run = response.json()
    assert run["finished_on"] is None
    assert [item["status"] for item in run["items"]] == ["to do", "to do"]


def test_update_run_item_tracks_attempts(client):
    run = client.post("/api/runs", json={"claim_ids": ["CLM-1001"]}).json()

    response = client.post(
        f"/api/runs/{run['run_id']}/items/CLM-1001",
        json={"status": "in progress", "note": ""},
    )
    assert response.json() == {
        "claim_id": "CLM-1001",
        "status": "in progress",
        "attempts": 1,
        "note": "",
    }

    response = client.post(
        f"/api/runs/{run['run_id']}/items/CLM-1001",
        json={"status": "done", "note": "Decided: approve for $420.00"},
    )
    assert response.json()["status"] == "done"
    assert response.json()["attempts"] == 1


def test_update_run_item_unknown_claim_is_404(client):
    run = client.post("/api/runs", json={"claim_ids": ["CLM-1001"]}).json()
    response = client.post(
        f"/api/runs/{run['run_id']}/items/CLM-9999",
        json={"status": "done", "note": ""},
    )
    assert response.status_code == 404


def test_finish_run_blocked_while_items_outstanding(client):
    run = client.post("/api/runs", json={"claim_ids": ["CLM-1001", "CLM-1002"]}).json()
    client.post(
        f"/api/runs/{run['run_id']}/items/CLM-1001",
        json={"status": "done", "note": "Decided"},
    )

    response = client.post(f"/api/runs/{run['run_id']}/finish", json={"summary": "x"})
    assert response.status_code == 409
    assert "CLM-1002" in response.json()["detail"]


def test_finish_run_succeeds_once_all_items_settled(client):
    run = client.post("/api/runs", json={"claim_ids": ["CLM-1001", "CLM-1002"]}).json()
    client.post(
        f"/api/runs/{run['run_id']}/items/CLM-1001",
        json={"status": "done", "note": "Decided"},
    )
    client.post(
        f"/api/runs/{run['run_id']}/items/CLM-1002",
        json={"status": "left for a handler", "note": "Failed twice"},
    )

    response = client.post(
        f"/api/runs/{run['run_id']}/finish", json={"summary": "Worked 2 claims."}
    )
    assert response.status_code == 200
    assert response.json()["summary"] == "Worked 2 claims."
    assert response.json()["finished_on"] is not None

    current = client.get("/api/runs/current").json()
    assert current["run_id"] == run["run_id"]
    assert current["summary"] == "Worked 2 claims."


def test_get_current_run_404_when_none_started(client):
    response = client.get("/api/runs/current")
    assert response.status_code == 404


def test_requeue_claim(client):
    client.post("/api/claims/CLM-1001/steps", json={"text": "started"})
    assert client.get("/api/claims/CLM-1001").json()["status"] == "in progress"

    response = client.post("/api/claims/CLM-1001/requeue")
    assert response.status_code == 200
    assert response.json()["status"] == "waiting"


def test_requeue_starts_a_new_thread(client):
    assert client.get("/api/claims/CLM-1001").json()["thread"] == 1
    client.post("/api/claims/CLM-1001/requeue")
    assert client.get("/api/claims/CLM-1001").json()["thread"] == 2


def test_requeue_decided_claim_is_blocked(client):
    client.post(
        "/api/claims/CLM-1001/decision",
        json={
            "decision": "approve",
            "payout": 420.0,
            "reason": "Routine trip delay with receipts.",
            "policy_reference": "Section 3",
        },
    )
    response = client.post("/api/claims/CLM-1001/requeue")
    assert response.status_code == 409
