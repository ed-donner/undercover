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

    assert work.work_claim(run_id, "CLM-1001", decide) == "Approved $100.00"

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
    assert outcome == "Approved $100.00"
    assert item(backend)["status"] == "done"


def test_a_stopped_claim_carries_on_without_a_new_attempt(backend, run_id):
    api.update_run_item(run_id, "CLM-1001", "in progress", "")
    api.record_step("CLM-1001", "started")

    def decide(claim_id):
        api.decide_claim(claim_id, **DECISION)
        return "Approved for $100.00."

    work.work_claim(run_id, "CLM-1001", decide)

    assert item(backend)["attempts"] == 1
    assert item(backend)["status"] == "done"


def test_a_claim_that_failed_starts_afresh_on_a_new_thread(backend, run_id):
    def decide(claim_id):
        api.record_step(claim_id, "started")
        if api.get_claim(claim_id)["thread"] == 1:
            raise RuntimeError("boom")
        api.decide_claim(claim_id, **DECISION)
        return "Approved for $100.00."

    work.work_claim(run_id, "CLM-1001", decide)

    assert api.get_claim("CLM-1001")["thread"] == 2
    assert item(backend)["attempts"] == 2
    assert item(backend)["status"] == "done"


def test_a_referral_is_left_for_a_handler_in_one_line(backend, run_id):
    def decide(claim_id):
        refer = {**DECISION, "decision": "refer", "payout": Decimal(0)}
        api.decide_claim(claim_id, **refer)
        return "A long\nmulti-line account of the referral."

    outcome = work.work_claim(run_id, "CLM-1001", decide)

    assert outcome == "Referred"
    assert item(backend)["status"] == "left for a handler"
    assert item(backend)["note"] == "Referred"
    assert item(backend)["attempts"] == 1


def test_a_held_approval_is_done_and_says_it_waits(backend, run_id):
    def decide(claim_id):
        api.decide_claim(claim_id, **{**DECISION, "payout": Decimal("2000.00")})
        return "Approved."

    work.work_claim(run_id, "CLM-1001", decide)

    assert item(backend)["status"] == "done"
    assert item(backend)["note"] == "Approved $2,000.00, waiting for sign-off"
