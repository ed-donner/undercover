from decimal import Decimal

import pytest

from agent import api, work

DECISION = {
    "decision": "approve",
    "payout": Decimal("100.00"),
    "reason": "Stubbed.",
    "policy_reference": "Section 1",
}


def item(backend):
    return backend.get("/api/runs/current").json()["items"][0]


@pytest.fixture
def run_id():
    return api.start_run(["CLM-1001"])


def test_retries_once_then_succeeds(backend, run_id):
    attempts = []

    def decide(claim_id):
        attempts.append(claim_id)
        if len(attempts) == 1:
            api.record_step(claim_id, "started")
            raise RuntimeError("boom")
        api.decide_claim(claim_id, **DECISION)
        return "Approved for $100.00."

    assert work.work_claim(run_id, "CLM-1001", decide) == "Approved for $100.00."

    assert len(attempts) == 2
    assert api.get_claim("CLM-1001")["status"] == "decided"
    assert item(backend)["status"] == "done"
    assert item(backend)["attempts"] == 2


def test_leaves_for_a_handler_after_two_failures(backend, run_id):
    def decide(claim_id):
        api.record_step(claim_id, "started")
        raise RuntimeError("boom")

    outcome = work.work_claim(run_id, "CLM-1001", decide)

    assert "left for a handler" in outcome.lower()
    assert api.get_claim("CLM-1001")["status"] == "waiting"
    assert item(backend)["status"] == "left for a handler"
    assert item(backend)["attempts"] == 2


def test_does_not_retry_a_claim_already_decided(backend, run_id):
    attempts = []

    def decide(claim_id):
        attempts.append(claim_id)
        api.decide_claim(claim_id, **DECISION)
        raise RuntimeError("dropped on the way back")

    outcome = work.work_claim(run_id, "CLM-1001", decide)

    assert len(attempts) == 1
    assert "decided" in outcome.lower()
    assert item(backend)["status"] == "done"
