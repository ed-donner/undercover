import time

import pytest

from agent import agents, api, lease, work
from backend import claims


def test_the_lease_is_held_inside_the_block_and_released_after(backend):
    with lease.held("CLM-1001") as free:
        assert free
        assert api.acquire_lease("CLM-1001", "someone-else") is None

    assert api.acquire_lease("CLM-1001", "someone-else") is not None


def test_a_claim_leased_to_another_agent_is_not_free(backend):
    api.acquire_lease("CLM-1001", "someone-else")

    with lease.held("CLM-1001") as free:
        assert not free


def test_the_lease_is_released_when_the_work_fails(backend):
    with pytest.raises(RuntimeError), lease.held("CLM-1001"):
        raise RuntimeError("boom")

    assert api.acquire_lease("CLM-1001", "someone-else") is not None


def test_renewing_keeps_the_lease_past_its_length(backend, monkeypatch):
    monkeypatch.setattr(claims, "LEASE_SECONDS", 1)
    monkeypatch.setattr(lease, "RENEWALS_PER_LEASE", 20)

    with lease.held("CLM-1001"):
        time.sleep(1.3)
        assert api.acquire_lease("CLM-1001", "someone-else") is None


def test_an_agent_leaves_a_claim_another_agent_is_working(backend):
    api.acquire_lease("CLM-1001", "someone-else")

    outcome = agents.decide_claim("CLM-1001")

    assert outcome == "CLM-1001 is being worked by another agent."


def test_a_run_item_for_a_claim_worked_elsewhere_is_done(backend):
    run_id = api.start_run(["CLM-1001"])
    api.acquire_lease("CLM-1001", "someone-else")

    outcome = work.work_claim(run_id, "CLM-1001", agents.decide_claim)

    assert outcome == work.BUSY_NOTE
    item = api.get_current_run()["items"][0]
    assert (item["status"], item["note"]) == ("done", work.BUSY_NOTE)
    assert api.get_claim("CLM-1001")["thread"] == 1
