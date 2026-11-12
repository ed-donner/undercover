from decimal import Decimal

from fastapi.testclient import TestClient

from agent import agents, api, service
from agent.tests.test_claim_graph import CLAIM, decision, sign_off


def test_a_signed_off_claim_is_paid_when_the_agent_comes_back(backend, script, saver):
    agents.decide_claim(CLAIM, script(decision(payout="1200.00"), "Done."), saver)
    sign_off(backend)
    assert api.get_claim(CLAIM)["paid_amount"] is None

    agents.carry_on(script(), saver)

    assert api.get_claim(CLAIM)["paid_amount"] == "1200.00"
    assert api.list_unfinished_claims() == []


def test_a_stopped_run_is_finished_by_the_next_run(monkeypatch, backend, script):
    def fake_decide(claim_id):
        api.decide_claim(claim_id, "approve", Decimal("100.00"), "Stubbed.", "S1")
        return f"Approved {claim_id}."

    monkeypatch.setattr(agents, "decide_claim", fake_decide)
    first, second = "CLM-1001", "CLM-1002"
    stopped = api.start_run([first, second])
    api.update_run_item(stopped, first, "in progress", "")
    api.record_step(first, "started")
    llm = script(
        ("work_claim", {"claim_id": first}),
        ("work_claim", {"claim_id": second}),
        ("finish_run", {"summary": "Finished."}),
        "Done.",
    )

    agents.run_queue(cap=1, llm=llm)

    run = api.get_current_run()
    assert run["run_id"] == stopped
    assert run["finished_on"] is not None
    assert {i["claim_id"]: i["attempts"] for i in run["items"]} == {first: 1, second: 1}


def test_the_service_carries_on_with_a_signed_off_claim(backend, script, saver):
    agents.decide_claim(CLAIM, script(decision(payout="1200.00"), "Done."), saver)
    sign_off(backend)
    service.app.dependency_overrides[service.claim_worker] = lambda: (
        lambda claim_id: agents.decide_claim(claim_id, script(), saver)
    )
    try:
        response = TestClient(service.app).post(f"/api/claims/{CLAIM}/resume")
    finally:
        service.app.dependency_overrides.clear()

    assert response.status_code == 202
    assert api.get_claim(CLAIM)["paid_amount"] == "1200.00"
