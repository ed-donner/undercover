import json

import pytest
from langchain_core.messages import AIMessage

from agent import base, main, tools
from agent.tests.stub import StubModel, claim_script, queue_script
from backend import db


def stub(responder):
    return StubModel(responder=responder)


def claim(client, claim_id):
    return client.get(f"/api/claims/{claim_id}").json()


def statuses(client):
    return [c["status"] for c in client.get("/api/claims").json()]


def scripts(**by_claim):
    """Claim scripts: a decline by default, or the (decision, payout) given."""

    def for_claim(claim_id):
        decision, payout = by_claim.get(claim_id.replace("-", "_"), ("decline", 0))
        return claim_script(claim_id, decision, payout)

    return for_claim


def test_model_defaults_to_deepseek_and_name_overrides(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_NAME", raising=False)
    default = base.model()
    assert default.model_name == "deepseek/deepseek-v4.1-flash"
    assert default.reasoning_effort == "low"
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    assert base.model().model_name == "openrouter/free"


def test_one_claim_run_decides_and_leaves_steps(client):
    line = main.run("CLM-1001", "t", stub(claim_script("CLM-1001", "approve", 420.0)))
    assert line == "CLM-1001: approved $420.00, paid"
    done = claim(client, "CLM-1001")
    assert done["status"] == "decided"
    assert done["paid"] == 420.0
    reads = [s["text"] for s in done["steps"] if s["kind"] == "read"]
    assert reads == [
        "Read policy_wording section 3: Trip Delay",
        "Read claims_manual section 9: Repeat claims",
    ]
    run = client.get("/api/runs/current").json()
    assert run["todos"] == [{"text": "CLM-1001", "status": "done"}]
    assert run["summary"] == line


def test_claim_agent_starts_clean_with_small_instructions(client):
    seen = []

    def spy(messages):
        seen.append(messages)
        return claim_script("CLM-1001")(messages)

    main.run("CLM-1001", "t", stub(spy))
    first = seen[0]
    assert [m.type for m in first] == ["system", "human"]
    manual = (db.DATA / "claims_manual.md").read_text()
    assert len(str(first[0].content)) < len(manual) / 2


def test_payout_over_the_limit_waits_for_sign_off(client):
    line = main.run("CLM-1001", "t", stub(claim_script("CLM-1001", "approve", 1250.0)))
    assert line == "CLM-1001: approved $1,250.00, waiting for sign-off"
    assert claim(client, "CLM-1001")["paid"] is None


def test_the_agent_cannot_pay_over_the_limit(client):
    client.post("/api/runs", json={"limit": 1})
    client.post("/api/runs/1/claims/CLM-1001")
    by_name = {t.name: t for t in tools.claim_tools("CLM-1001")}
    by_name["decide"].invoke(
        {
            "decision": "approve",
            "payout": 1250.0,
            "policy_section": "3",
            "reason": "Ok.",
        }
    )
    refused = json.loads(by_name["pay"].invoke({"amount": 1250.0}))
    assert "sign off" in refused["detail"]
    assert claim(client, "CLM-1001")["paid"] is None


def test_a_claim_with_no_decision_counts_as_a_failure(client):
    main.run("CLM-1001", "t", stub(lambda m: AIMessage(content="I give up.")))
    assert claim(client, "CLM-1001")["status"] == "waiting"
    assert claim(client, "CLM-1001")["attempts"] == 1


def test_queue_run_respects_the_cap(client):
    summary = main.run_queue(3, "t", stub(queue_script(scripts())))
    assert summary == "Summary: the run is finished."
    assert statuses(client).count("waiting") == 22
    assert statuses(client).count("in_progress") == 0
    run = client.get("/api/runs/current").json()
    assert len(run["claims"]) == 3
    assert run["summary"] == summary


def test_queue_todo_list_ends_done(client):
    main.run_queue(3, "t", stub(queue_script(scripts())))
    todos = client.get("/api/runs/current").json()["todos"]
    assert [t["text"] for t in todos] == ["CLM-1001", "CLM-1002", "CLM-1003"]
    assert {t["status"] for t in todos} == {"done"}


def failing(bad, times):
    """Claim scripts where one claim raises a provider error some number of times."""
    attempts = {"n": 0}

    def for_claim(claim_id):
        good = claim_script(claim_id)

        def respond(messages):
            if claim_id == bad and not any(m.type == "tool" for m in messages):
                attempts["n"] += 1
                if attempts["n"] <= times:
                    raise TimeoutError("model provider timed out")
            return good(messages)

        return respond

    return for_claim


def test_a_failed_claim_does_not_stop_the_run(client):
    main.run_queue(3, "t", stub(queue_script(failing("CLM-1002", 5))))
    by_id = {c["claim_id"]: c["status"] for c in client.get("/api/claims").json()}
    assert by_id["CLM-1001"] == "decided"
    assert by_id["CLM-1003"] == "decided"
    assert "in_progress" not in by_id.values()


def test_a_failed_claim_goes_back_and_is_tried_again(client):
    script = queue_script(failing("CLM-1002", 1), retry=frozenset({"CLM-1002"}))
    main.run_queue(3, "t", stub(script))
    retried = claim(client, "CLM-1002")
    assert retried["status"] == "decided"
    assert retried["attempts"] == 1
    kinds = [s["kind"] for s in retried["steps"]]
    assert kinds.count("failure") == 1
    assert kinds.count("decision") == 1


def test_a_claim_that_fails_twice_is_left_for_a_handler(client):
    script = queue_script(failing("CLM-1002", 5), retry=frozenset({"CLM-1002"}))
    main.run_queue(3, "t", stub(script))
    left = claim(client, "CLM-1002")
    assert left["status"] == "for_handler"
    todos = client.get("/api/runs/current").json()["todos"]
    assert {t["text"]: t["status"] for t in todos}["CLM-1002"] == "for_handler"


def test_the_check_for_missed_claims_works_them(client):
    script = queue_script(scripts(), skip=frozenset({"CLM-1003"}))
    summary = main.run_queue(3, "t", stub(script))
    assert claim(client, "CLM-1003")["status"] == "decided"
    assert "Not worked" not in summary


def test_missed_claims_that_stay_missed_are_reported(client):
    def lazy(messages):
        return AIMessage(content="Done.")

    summary = main.run_queue(2, "t", stub(lazy))
    assert "Not worked: CLM-1001, CLM-1002." in summary


def test_a_claim_is_never_decided_twice(client):
    main.run("CLM-1001", "t", stub(claim_script("CLM-1001", "approve", 420.0)))
    again = client.post(
        "/api/claims/CLM-1001/decision",
        json={"decision": "decline", "payout": 0, "policy_section": "3", "reason": "x"},
    )
    assert again.status_code == 409
    assert main.run("CLM-1001", "t", stub(claim_script("CLM-1001"))).startswith(
        "CLM-1001: not started"
    )


def test_cli_runs_one_claim_or_the_queue(client, monkeypatch, capsys):
    monkeypatch.setattr(main, "model", lambda: stub(queue_script(scripts())))
    monkeypatch.setattr("sys.argv", ["agent", "--claim", "CLM-1001"])
    main.cli()
    assert capsys.readouterr().out.startswith("CLM-1001: decline")
    monkeypatch.setattr("sys.argv", ["agent", "--limit", "2"])
    main.cli()
    assert "finished" in capsys.readouterr().out
    assert statuses(client).count("decided") == 3


@pytest.mark.usefixtures("client")
def test_instructions_come_from_the_backend():
    assert "Working a claim" in tools.instructions()["claim"]
