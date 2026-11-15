from backend import db
from backend.documents import sections


def new_run(client, limit):
    return client.post("/api/runs", json={"limit": limit}).json()["id"]


def waiting(client, run_id):
    return [c["claim_id"] for c in client.get(f"/api/runs/{run_id}/waiting").json()]


def fail(client, claim_id):
    return client.post(
        f"/api/claims/{claim_id}/failure", json={"error": "timeout"}
    ).json()


def test_limit_caps_the_claims_offered_and_started(client):
    run_id = new_run(client, 3)
    assert waiting(client, run_id) == ["CLM-1001", "CLM-1002", "CLM-1003"]
    for claim_id in waiting(client, run_id):
        assert client.post(f"/api/runs/{run_id}/claims/{claim_id}").status_code == 200
    assert waiting(client, run_id) == []
    assert client.post(f"/api/runs/{run_id}/claims/CLM-1004").status_code == 409
    statuses = [c["status"] for c in client.get("/api/claims").json()]
    assert statuses.count("waiting") == 22


def test_a_started_claim_cannot_be_started_again(client):
    run_id = new_run(client, 3)
    client.post(f"/api/runs/{run_id}/claims/CLM-1001")
    assert client.post(f"/api/runs/{run_id}/claims/CLM-1001").status_code == 409


def test_first_failure_requeues_and_second_leaves_it_for_a_handler(client):
    run_id = new_run(client, 1)
    client.post(f"/api/runs/{run_id}/claims/CLM-1001")
    assert fail(client, "CLM-1001") == {"status": "waiting", "attempts": 1}
    assert waiting(client, run_id) == ["CLM-1001"]
    client.post(f"/api/runs/{run_id}/claims/CLM-1001")
    assert fail(client, "CLM-1001") == {"status": "for_handler", "attempts": 2}
    assert waiting(client, run_id) == []
    steps = client.get("/api/claims/CLM-1001").json()["steps"]
    assert [s["kind"] for s in steps].count("failure") == 2


def test_a_decided_claim_cannot_fail_or_restart(client):
    run_id = new_run(client, 1)
    client.post(f"/api/runs/{run_id}/claims/CLM-1001")
    decline = {
        "decision": "decline",
        "payout": 0,
        "policy_section": "3",
        "reason": "No.",
    }
    client.post("/api/claims/CLM-1001/decision", json=decline)
    assert (
        client.post("/api/claims/CLM-1001/failure", json={"error": "x"}).status_code
        == 409
    )
    assert client.post(f"/api/runs/{run_id}/claims/CLM-1001").status_code == 409


def test_todos_are_stored_replaced_and_shown_in_order(client):
    run_id = new_run(client, 2)
    first = [
        {"text": "CLM-1001", "status": "todo"},
        {"text": "CLM-1002", "status": "todo"},
    ]
    client.put(f"/api/runs/{run_id}/todos", json={"items": first})
    second = [
        {"text": "CLM-1001", "status": "done"},
        {"text": "CLM-1002", "status": "in_progress"},
    ]
    client.put(f"/api/runs/{run_id}/todos", json={"items": second})
    run = client.get("/api/runs/current").json()
    assert run["id"] == run_id
    assert run["todos"] == second


def test_bad_todo_status_is_refused(client):
    run_id = new_run(client, 1)
    items = [{"text": "x", "status": "finished"}]
    assert (
        client.put(f"/api/runs/{run_id}/todos", json={"items": items}).status_code
        == 422
    )


def test_no_current_run_before_any_run(client):
    assert client.get("/api/runs/current").json() is None
    assert client.get("/api/runs/99").status_code == 404


def test_finish_run_stores_the_summary(client):
    run_id = new_run(client, 1)
    client.post(f"/api/runs/{run_id}/summary", json={"summary": "All done."})
    run = client.get(f"/api/runs/{run_id}").json()
    assert (run["summary"], run["finished"]) == ("All done.", True)


def test_sections_of_the_manual_and_wording(client):
    listed = client.get("/api/documents/claims_manual/sections").json()
    assert len(listed) == 14
    assert listed[8] == {"number": 9, "title": "Repeat claims"}
    assert len(client.get("/api/documents/policy_wording/sections").json()) == 12
    assert client.get("/api/documents/evals/sections").status_code == 422
    assert str(sections("claims_manual")[8]["text"]).startswith("## 9. Repeat claims")


def test_reading_a_section_leaves_a_step(client):
    client.post("/api/runs/1/claims/CLM-1001")
    response = client.post(
        "/api/claims/CLM-1001/read-section",
        json={"document": "claims_manual", "number": 9},
    )
    assert "third claim within any 12 month period" in response.json()["text"]
    steps = client.get("/api/claims/CLM-1001").json()["steps"]
    assert steps[-1]["text"] == "Read claims_manual section 9: Repeat claims"
    missing = {"document": "claims_manual", "number": 99}
    assert (
        client.post("/api/claims/CLM-1001/read-section", json=missing).status_code
        == 404
    )


def test_instructions_cover_the_queue_and_a_claim(client):
    instructions = client.get("/api/instructions").json()
    assert "Running the queue" in instructions["queue"]
    assert "Working a claim" in instructions["claim"]


def test_reseed_resets_everything(client):
    run_id = new_run(client, 1)
    client.post(f"/api/runs/{run_id}/claims/CLM-1001")
    assert client.post("/api/reseed").json() == {"claims": 25}
    assert client.get("/api/claims/CLM-1001").json()["status"] == "waiting"
    assert client.get("/api/runs/current").json() is None
    assert db.DB_PATH.exists()
