from agent import cli


def test_main_runs_one_named_claim(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(cli, "run", lambda claim_id, thread_id: calls.append(claim_id))
    monkeypatch.setattr(cli, "run_queue", lambda cap=None: calls.append(("queue", cap)))
    monkeypatch.setattr("sys.argv", ["cli.py", "--claim", "CLM-1001"])

    cli.main()

    assert calls == ["CLM-1001"]


def test_main_runs_a_capped_queue(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "run", lambda claim_id, thread_id: calls.append(claim_id))
    monkeypatch.setattr(cli, "run_queue", lambda cap=None: calls.append(("queue", cap)))
    monkeypatch.setattr("sys.argv", ["cli.py", "--cap", "5"])

    cli.main()

    assert calls == [("queue", 5)]


def test_main_runs_the_whole_queue_by_default(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "run", lambda claim_id, thread_id: calls.append(claim_id))
    monkeypatch.setattr(cli, "run_queue", lambda cap=None: calls.append(("queue", cap)))
    monkeypatch.setattr("sys.argv", ["cli.py"])

    cli.main()

    assert calls == [("queue", None)]
