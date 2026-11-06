import json

import pytest
from langchain_core.messages import AIMessage

from agent import __main__ as cli
from agent import claim_agent, common, queue_agent
from agent.tests.stubs import api, calls, claim, decision, stub
from backend.main import INSTRUCTIONS


def declines(claim_id):
    return stub(
        calls(("record_decision", decision(claim_id, "decline", 0))),
        AIMessage(content="Declined."),
    )


def fails():
    return stub(failures=99)


@pytest.fixture
def claim_models(monkeypatch):
    """Play out each claim's attempts with the stub models listed for it."""
    models = {}
    attempt = claim_agent.attempt
    monkeypatch.setattr(
        claim_agent,
        "attempt",
        lambda claim_id: attempt(claim_id, models[claim_id].pop(0)),
    )
    return models


def work(*claim_ids):
    return [calls(("work_claim", {"claim_id": claim_id})) for claim_id in claim_ids]


def latest_run():
    return api.get("/api/runs/latest").json()


def statuses():
    return {
        entry["claim_id"]: entry["status"] for entry in api.get("/api/claims").json()
    }


def test_a_run_works_no_more_claims_than_its_cap(claim_models, capsys):
    for claim_id in ("CLM-1013", "CLM-1007", "CLM-1009"):
        claim_models[claim_id] = [declines(claim_id)]
    model = stub(
        *work("CLM-1013", "CLM-1007", "CLM-1009"),
        AIMessage(content="Worked two claims."),
    )
    assert queue_agent.run(2, [], model) == "Worked two claims."
    lines = capsys.readouterr().out.splitlines()
    assert lines[2] == (
        "This run is capped at 2 claims and has started 2, so leave CLM-1009 waiting."
    )
    left_waiting = [
        claim_id for claim_id, status in statuses().items() if status != "waiting"
    ]
    assert left_waiting == ["CLM-1007", "CLM-1013"]


def test_the_to_do_list_is_saved_on_the_run(claim_models):
    claim_models["CLM-1013"] = [declines("CLM-1013")]
    todo = {"content": "Work CLM-1013", "status": "in_progress"}
    model = stub(
        calls(("write_todos", {"todos": [todo]})),
        *work("CLM-1013"),
        calls(("write_todos", {"todos": [{**todo, "status": "done"}]})),
        AIMessage(content="Declined one claim."),
    )
    queue_agent.run(None, ["CLM-1013"], model)
    run = latest_run()
    assert run["todos"] == [{"content": "Work CLM-1013", "status": "done"}]
    assert run["summary"] == "Declined one claim."
    assert run["finished_at"]


def test_a_failed_claim_doesnt_stop_the_run_and_is_tried_again(claim_models, capsys):
    claim_models["CLM-1002"] = [fails(), declines("CLM-1002")]
    claim_models["CLM-1003"] = [declines("CLM-1003")]
    model = stub(
        *work("CLM-1002", "CLM-1003", "CLM-1002"),
        AIMessage(content="Two claims declined."),
    )
    queue_agent.run(2, [], model)
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("CLM-1002 failed")
    assert lines[0].endswith("It's back in the queue for one more try.")
    assert lines[1:3] == ["CLM-1003: declined.", "CLM-1002: declined."]
    assert claim("CLM-1002")["attempts"] == 1
    assert statuses()["CLM-1002"] == "decided"


def test_a_claim_that_fails_twice_is_left_for_a_handler(claim_models, capsys):
    claim_models["CLM-1002"] = [fails(), fails()]
    model = stub(*work("CLM-1002", "CLM-1002"), AIMessage(content="One left."))
    assert queue_agent.run(None, ["CLM-1002"], model) == "One left."
    assert capsys.readouterr().out.splitlines()[1].endswith("It's left for a handler.")
    assert claim("CLM-1002")["status"] == "left_for_handler"
    assert latest_run()["summary"] == "One left."


def test_the_run_is_sent_back_for_a_claim_it_missed(claim_models, monkeypatch):
    claim_models["CLM-1013"] = [declines("CLM-1013")]
    claim_models["CLM-1007"] = [declines("CLM-1007")]
    reminders = []
    missed = queue_agent.Run.missed
    monkeypatch.setattr(
        queue_agent.Run,
        "missed",
        lambda self: reminders.append(missed(self)) or reminders[-1],
    )
    model = stub(
        *work("CLM-1013"),
        AIMessage(content="Done early."),
        *work("CLM-1007"),
        AIMessage(content="All done."),
    )
    assert queue_agent.run(None, ["CLM-1013", "CLM-1007"], model) == "All done."
    assert reminders[0] == (
        "Before you finish, there's work left in this run. The run can start 1 more"
        " of these waiting claims: CLM-1007. Work them, then finish with your summary."
    )
    assert reminders[-1] is None
    assert statuses()["CLM-1007"] == "decided"


def test_the_run_is_sent_back_for_a_claim_waiting_for_another_try(claim_models):
    claim_models["CLM-1002"] = [fails(), declines("CLM-1002")]
    model = stub(
        *work("CLM-1002"),
        AIMessage(content="Done early."),
        *work("CLM-1002"),
        AIMessage(content="All done."),
    )
    assert queue_agent.run(1, [], model) == "All done."
    assert statuses()["CLM-1002"] == "decided"


def test_a_run_that_keeps_finishing_early_is_reminded_twice():
    model = stub(*[AIMessage(content="Done.") for _ in range(3)])
    assert queue_agent.run(None, ["CLM-1013", "CLM-1007"], model) == "Done."
    assert statuses()["CLM-1013"] == "waiting"


def test_a_run_that_has_used_its_cap_finishes_without_a_reminder(claim_models):
    claim_models["CLM-1013"] = [declines("CLM-1013")]
    model = stub(*work("CLM-1013"), AIMessage(content="Done."))
    assert queue_agent.run(1, [], model) == "Done."
    assert list(statuses().values()).count("waiting") == 24


def test_a_named_run_works_only_the_claims_named(claim_models, capsys):
    claim_models["CLM-1004"] = [declines("CLM-1004")]
    model = stub(*work("CLM-1005", "CLM-1004"), AIMessage(content="Done."))
    queue_agent.run(None, ["CLM-1004"], model)
    assert capsys.readouterr().out.splitlines()[0] == (
        "CLM-1005 isn't one of the claims named for this run."
    )
    assert statuses()["CLM-1005"] == "waiting"
    assert statuses()["CLM-1004"] == "decided"


def test_a_run_whose_model_keeps_failing_stops_with_no_claim_in_progress():
    with pytest.raises(ConnectionError):
        queue_agent.run(None, ["CLM-1013"], fails())
    assert latest_run()["summary"] == (
        "The run stopped: ConnectionError: The model provider timed out."
    )
    assert "in_progress" not in statuses().values()


def test_a_run_with_nothing_waiting_says_so():
    api.post("/api/claims/CLM-1013/start")
    assert queue_agent.run(None, ["CLM-1013"], fails()) == "No claims are waiting."
    assert latest_run()["summary"] == "No claims are waiting."


def test_the_queue_agent_sees_waiting_claims_without_customer_names():
    api.post("/api/claims/CLM-1001/start")
    queue = queue_agent.Run(run_id=1, cap=None, named=[])
    list_waiting_claims = queue_agent.tools(queue)[0]
    waiting = json.loads(list_waiting_claims.invoke({}))
    assert len(waiting) == 24
    assert set(waiting[0]) == set(queue_agent.CLAIM_FIELDS_FOR_THE_MODEL)
    assert "customer_name" not in waiting[0]


def test_the_queue_agent_works_from_its_own_instructions(monkeypatch):
    prompts = []

    def create_agent(*args, system_prompt, **kwargs):
        prompts.append(system_prompt)
        return real_create_agent(*args, system_prompt=system_prompt, **kwargs)

    real_create_agent = queue_agent.create_agent
    monkeypatch.setattr(queue_agent, "create_agent", create_agent)
    queue_agent.run(1, [], stub(*[AIMessage(content="Done.") for _ in range(3)]))
    assert prompts == [(INSTRUCTIONS / "queue.md").read_text(encoding="utf-8")]


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        ([], (None, [])),
        (["--cap", "5"], (5, [])),
        (["CLM-1001", "CLM-1004"], (None, ["CLM-1001", "CLM-1004"])),
    ],
)
def test_the_command_line(monkeypatch, capsys, arguments, expected):
    runs = []
    monkeypatch.setattr(
        queue_agent,
        "run",
        lambda cap, claim_ids: runs.append((cap, claim_ids)) or "Summary.",
    )
    cli.main(arguments)
    assert runs == [expected]
    assert capsys.readouterr().out == "Summary.\n"


def test_the_command_line_prints_each_claim_then_the_summary(
    claim_models, monkeypatch, capsys
):
    claim_models["CLM-1013"] = [declines("CLM-1013")]
    model = stub(*work("CLM-1013"), AIMessage(content="One claim declined."))
    monkeypatch.setattr(common, "model", lambda: model)
    cli.main(["CLM-1013"])
    assert capsys.readouterr().out == "CLM-1013: declined.\nOne claim declined.\n"


def test_claims_asked_for_together_are_worked_one_at_a_time(claim_models):
    claim_models["CLM-1013"] = [declines("CLM-1013")]
    claim_models["CLM-1007"] = [declines("CLM-1007")]
    together = calls(
        ("work_claim", {"claim_id": "CLM-1013"}),
        ("work_claim", {"claim_id": "CLM-1007"}),
    )
    queue_agent.run(1, [], stub(together, AIMessage(content="Done.")))
    assert list(statuses().values()).count("decided") == 1
