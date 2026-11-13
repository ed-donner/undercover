import runpy
import sys
from contextlib import nullcontext

import httpx
import pytest
from fastapi.testclient import TestClient

from agent import cli
from backend.main import create_app

OUTCOMES = {
    "CLM-1001": ("approve", "420.00", True),
    "CLM-1003": ("approve", "1000.01", False),
    "CLM-1004": ("refer", "0", False),
}


def runner(claim_id: str, thread_id: str) -> str:
    if claim_id == "CLM-1002":
        raise RuntimeError("model unavailable")
    outcome, payout, pay = OUTCOMES.get(claim_id, ("decline", "0", False))
    path = f"/api/claims/{claim_id}"
    with cli.backend() as client:
        runs = client.get(f"{path}/runs").json()
        run_id = next(run["run_id"] for run in runs if run["thread_id"] == thread_id)
        decision = {
            "run_id": run_id,
            "outcome": outcome,
            "payout": payout,
            "calculation": "Calculation.",
            "explanation": "Explanation. Second sentence.",
            "policy_sections": [1],
            "manual_version": "2026.2",
            "manual_sections": [4],
        }
        for document_id, section in (("wording", 1), ("manual", 4)):
            client.post(
                f"{path}/reads",
                json={"run_id": run_id, "document_id": document_id, "section": section},
            )
        client.post(f"{path}/decision", json=decision)
        if pay:
            client.post(f"{path}/payment", json={"amount": payout})
    return "Done."


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "POLL_SECONDS", 0.01)
    with TestClient(create_app(tmp_path / "cli.db", runner=runner)) as test_client:
        monkeypatch.setattr(cli, "backend", lambda: nullcontext(test_client))
        yield test_client


def fake_backend(monkeypatch, handler):
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        cli, "backend", lambda: httpx.Client(base_url="http://x", transport=transport)
    )


def test_processes_every_waiting_claim_in_queue_order(api, capsys):
    queue = [claim["claim_id"] for claim in api.get("/api/claims").json()]
    with pytest.raises(SystemExit) as failure:
        cli.main([])
    assert failure.value.code == 1
    lines = capsys.readouterr().out.splitlines()
    assert [line.split(":")[0] for line in lines] == queue
    assert "CLM-1001: approve, $420.00, paid" in lines
    assert lines[1].startswith("CLM-1002: failed, Agent could not finish")
    states = {c["claim_id"]: c["status"] for c in api.get("/api/claims").json()}
    assert states["CLM-1002"] == "waiting"
    assert states["CLM-1003"] == "waiting_for_sign_off"
    assert "in_progress" not in states.values()


def test_named_claims(api, capsys):
    cli.main(["CLM-1001", "CLM-1003", "CLM-1004"])
    assert capsys.readouterr().out.splitlines() == [
        "CLM-1001: approve, $420.00, paid",
        "CLM-1003: approve, $1,000.01, waiting for sign-off",
        "CLM-1004: refer",
    ]


def test_claims_that_cannot_start(api, capsys):
    cli.main(["CLM-1001"])
    capsys.readouterr()
    with pytest.raises(SystemExit):
        cli.main(["CLM-1001", "NOPE"])
    assert capsys.readouterr().out.splitlines() == [
        "CLM-1001: not started (409)",
        "NOPE: not started (404)",
    ]


def test_no_waiting_claims(monkeypatch, capsys):
    fake_backend(monkeypatch, lambda request: httpx.Response(200, json=[]))
    cli.main([])
    assert capsys.readouterr().out == "No waiting claims.\n"


def test_unreachable_backend(monkeypatch):
    def refuse(request):
        raise httpx.ConnectError("refused")

    fake_backend(monkeypatch, refuse)
    with pytest.raises(SystemExit, match="npm run dev"):
        cli.main([])


def test_module_entry_point(api, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["agent", "CLM-1001"])
    runpy.run_module("agent", run_name="__main__")
    assert capsys.readouterr().out == "CLM-1001: approve, $420.00, paid\n"
