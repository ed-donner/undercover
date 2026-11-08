import pytest

from agent import __main__ as cli


@pytest.fixture
def calls(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "decide_claim", calls.append)
    monkeypatch.setattr(cli, "run_queue", lambda cap=None: calls.append(("queue", cap)))
    return calls


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["--claim", "CLM-1001"], ["CLM-1001"]),
        (["--cap", "5"], [("queue", 5)]),
        ([], [("queue", None)]),
    ],
)
def test_main(monkeypatch, calls, argv, expected):
    monkeypatch.setattr("sys.argv", ["cli.py", *argv])

    cli.main()

    assert calls == expected
