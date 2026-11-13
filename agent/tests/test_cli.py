import json
import runpy
import sys
from contextlib import contextmanager

import httpx
import pytest

from agent import api, cli


def backend_factory(handler):
    @contextmanager
    def connect():
        with httpx.Client(
            base_url="http://test", transport=httpx.MockTransport(handler)
        ) as client:
            yield api.BackendAPI(client)

    return connect


def setup_backend(monkeypatch, status="completed", technical_issues=0, error=None):
    calls = []
    reads = []

    def handler(request):
        calls.append(request)
        if request.method == "POST":
            return httpx.Response(202, json={"run_id": "run-1"})
        reads.append(request)
        return httpx.Response(
            200,
            json={
                "status": "running" if len(reads) == 1 else status,
                "summary": "5 claims worked.",
                "technical_issues": technical_issues,
                "error": error,
            },
        )

    monkeypatch.setattr(
        api,
        "connect",
        backend_factory(handler),
    )
    monkeypatch.setattr(cli, "POLL_SECONDS", 0)
    return calls


@pytest.mark.parametrize(
    ("args", "body"),
    [
        ([], {"mode": "queue", "max_claims": None}),
        (["--max-claims", "5"], {"mode": "queue", "max_claims": 5}),
        (["CLM-1001"], {"mode": "claim", "claim_id": "CLM-1001"}),
    ],
)
def test_single_top_level_start(monkeypatch, capsys, args, body):
    calls = setup_backend(monkeypatch)
    cli.main(args)
    starts = [request for request in calls if request.method == "POST"]
    assert len(starts) == 1
    assert starts[0].url.path == "/api/agent-runs"
    assert json.loads(starts[0].content) == body
    assert capsys.readouterr().out == "5 claims worked.\n"


def test_multiple_explicit_named_runs(monkeypatch):
    calls = setup_backend(monkeypatch)
    cli.main(["CLM-1001", "CLM-1002"])
    assert len([call for call in calls if call.method == "POST"]) == 2


@pytest.mark.parametrize(
    "args",
    [
        ["--max-claims", "0"],
        ["--max-claims", "-1"],
        ["--max-claims", "1.5"],
        ["CLM-1001", "--max-claims", "5"],
    ],
)
def test_invalid_arguments(args):
    with pytest.raises(SystemExit) as error:
        cli.main(args)
    assert error.value.code == 2


@pytest.mark.parametrize("status", [404, 409])
def test_cannot_start(monkeypatch, capsys, status):
    def handler(request):
        return httpx.Response(status, json={"detail": "Not eligible"})

    monkeypatch.setattr(
        api,
        "connect",
        backend_factory(handler),
    )
    with pytest.raises(SystemExit) as error:
        cli.main(["CLM-1001"])
    assert error.value.code == 1
    assert f"Not started ({status})" in capsys.readouterr().out


def test_technical_failure_exit_code(monkeypatch, capsys):
    setup_backend(monkeypatch, status="failed", error="Agent could not finish.")
    with pytest.raises(SystemExit) as error:
        cli.main([])
    assert error.value.code == 1
    assert "Agent could not finish." in capsys.readouterr().out
    setup_backend(monkeypatch, technical_issues=1)
    with pytest.raises(SystemExit):
        cli.main([])


def test_business_referral_is_not_a_technical_failure(monkeypatch):
    setup_backend(monkeypatch, technical_issues=0)
    cli.main([])


def test_unreachable_backend(monkeypatch):
    def handler(request):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(
        api,
        "connect",
        backend_factory(handler),
    )
    with pytest.raises(SystemExit, match="npm run dev"):
        cli.main([])


def test_module_entry_point(monkeypatch, capsys):
    setup_backend(monkeypatch)
    monkeypatch.setattr(sys, "argv", ["agent", "CLM-1001"])
    runpy.run_module("agent", run_name="__main__")
    assert "5 claims worked" in capsys.readouterr().out
