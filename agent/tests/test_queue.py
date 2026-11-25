import json

import pytest
from langchain_core.messages import AIMessage

from agent import queue
from agent.__main__ import main
from agent.tests.conftest import DOWN, decided, stub, tool_call


def todos(*items):
    return tool_call(
        "write_todos",
        todos=[
            {"claim_id": claim_id, "content": "Trip delay", "status": status}
            for claim_id, status in items
        ],
    )


def work(claim_id):
    return tool_call("work_claim", claim_id=claim_id)


FINISH = [tool_call("finish_run", summary="Two claims approved."), AIMessage("Done.")]


def start(client, cap):
    return client.post("/api/runs", json={"cap": cap}).json()["id"]


def statuses(client):
    return {c["claim_id"]: c["status"] for c in client.get("/api/claims").json()}


def run(client, run_id):
    return client.get(f"/api/runs/{run_id}").json()


def tool_results(llm, name):
    return [m.content for m in llm.seen[-1] if getattr(m, "name", None) == name]


def test_a_capped_run(client):
    run_id = start(client, 2)
    llm = stub(
        tool_call("list_waiting_claims"),
        todos(("CLM-1001", "todo"), ("CLM-1002", "todo")),
        todos(("CLM-1001", "in_progress"), ("CLM-1002", "todo")),
        work("CLM-1001"),
        *decided("CLM-1001"),
        todos(("CLM-1001", "done"), ("CLM-1002", "in_progress")),
        work("CLM-1002"),
        *decided("CLM-1002"),
        todos(("CLM-1001", "done"), ("CLM-1002", "done")),
        *FINISH,
    )
    queue.run_queue(run_id, llm)
    listing = json.loads(tool_results(llm, "list_waiting_claims")[0])
    assert listing["cap"] == 2
    assert listing["new_claims_left"] == 2
    assert len(listing["claims"]) == 25
    assert set(listing["claims"][0]) == set(queue.CLAIM_FIELDS)
    assert "CLM-1001: approve, $100.00" in tool_results(llm, "work_claim")[0]
    finished = run(client, run_id)
    assert finished["status"] == "finished"
    assert finished["summary"] == "Two claims approved."
    assert [t["status"] for t in finished["todos"]] == ["done", "done"]
    counts = list(statuses(client).values())
    assert counts.count("decided") == 2
    assert counts.count("waiting") == 23


def test_the_cap_holds(client):
    run_id = start(client, 1)
    llm = stub(work("CLM-1001"), *decided("CLM-1001"), work("CLM-1002"), *FINISH)
    queue.run_queue(run_id, llm)
    assert tool_results(llm, "work_claim")[1] == (
        "Refused: the run has already worked its cap of 1"
    )
    assert statuses(client)["CLM-1002"] == "waiting"
    assert run(client, run_id)["status"] == "finished"


def test_a_failed_claim_does_not_stop_the_run(client):
    run_id = start(client, 1)
    llm = stub(
        work("CLM-1001"),
        *DOWN,
        work("CLM-1001"),
        *decided("CLM-1001"),
        *FINISH,
    )
    queue.run_queue(run_id, llm)
    assert tool_results(llm, "work_claim")[0].endswith("back in the queue")
    assert statuses(client)["CLM-1001"] == "decided"
    assert run(client, run_id)["status"] == "finished"


def test_a_failed_claim_is_retried_later_and_counts_once(client):
    run_id = start(client, 2)
    llm = stub(
        todos(("CLM-1001", "todo"), ("CLM-1002", "todo")),
        work("CLM-1001"),
        *DOWN,
        todos(("CLM-1001", "todo"), ("CLM-1002", "todo")),
        work("CLM-1002"),
        *decided("CLM-1002"),
        work("CLM-1001"),
        *decided("CLM-1001"),
        todos(("CLM-1001", "done"), ("CLM-1002", "done")),
        *FINISH,
    )
    queue.run_queue(run_id, llm)
    found = statuses(client)
    assert found["CLM-1001"] == "decided"
    assert found["CLM-1002"] == "decided"
    assert list(found.values()).count("waiting") == 23
    steps = client.get("/api/claims/CLM-1001/steps").json()
    assert ("attempt", "Attempt 2") in [(s["kind"], s["content"]) for s in steps]
    assert run(client, run_id)["status"] == "finished"


def test_a_claim_that_fails_twice_is_left_for_a_handler(client):
    run_id = start(client, 1)
    llm = stub(
        work("CLM-1001"),
        *DOWN,
        work("CLM-1001"),
        *DOWN,
        todos(("CLM-1001", "handler")),
        *FINISH,
    )
    queue.run_queue(run_id, llm)
    assert tool_results(llm, "work_claim")[1].endswith("left for a handler")
    assert statuses(client)["CLM-1001"] == "needs_handler"
    finished = run(client, run_id)
    assert finished["todos"][0]["status"] == "handler"
    assert finished["status"] == "finished"


def test_finish_is_refused_while_a_claim_is_missed(client):
    run_id = start(client, 2)
    llm = stub(
        work("CLM-1001"),
        *decided("CLM-1001"),
        tool_call("finish_run", summary="Done early."),
        work("CLM-1002"),
        *decided("CLM-1002"),
        *FINISH,
    )
    queue.run_queue(run_id, llm)
    assert tool_results(llm, "finish_run")[0] == (
        "Refused: CLM-1002 still waiting within the run. Work them before you finish."
    )
    assert statuses(client)["CLM-1002"] == "decided"
    assert run(client, run_id)["summary"] == "Two claims approved."


def test_finish_is_refused_while_a_retry_is_due(client):
    run_id = start(client, 1)
    llm = stub(
        work("CLM-1001"),
        *DOWN,
        tool_call("finish_run", summary="Done early."),
        work("CLM-1001"),
        *decided("CLM-1001"),
        *FINISH,
    )
    queue.run_queue(run_id, llm)
    assert tool_results(llm, "finish_run")[0].startswith("Refused: CLM-1001")


def test_a_queue_agent_that_raises_fails_the_run(client):
    run_id = start(client, 2)
    client.post("/api/claims/CLM-1003/start")
    queue.run_queue(run_id, stub(*DOWN))
    failed = run(client, run_id)
    assert failed["status"] == "failed"
    assert failed["problem"] == "The run stopped with an error: model unavailable"
    assert "in_progress" not in statuses(client).values()


def test_a_run_the_agent_did_not_finish(client):
    run_id = start(client, 1)
    queue.run_queue(run_id, stub(AIMessage("I am done.")))
    finished = run(client, run_id)
    assert finished["status"] == "finished"
    assert finished["summary"] == "The agent stopped without writing a summary."


def test_a_one_claim_run(client):
    run_id = client.post("/api/claims/CLM-1003/run").json()["id"]
    llm = stub(
        tool_call("list_waiting_claims"),
        work("CLM-1001"),
        work("CLM-1003"),
        *decided("CLM-1003"),
        *FINISH,
    )
    queue.run_queue(run_id, llm)
    listing = json.loads(tool_results(llm, "list_waiting_claims")[0])
    assert [c["claim_id"] for c in listing["claims"]] == ["CLM-1003"]
    assert tool_results(llm, "work_claim")[0] == (
        "Refused: this run is for CLM-1003 only"
    )
    assert statuses(client)["CLM-1001"] == "waiting"
    assert statuses(client)["CLM-1003"] == "decided"
    assert llm.seen[0][1].content == "Please work claim CLM-1003 only."


def test_queue_tools():
    run = queue.Run(1, None, 5, stub())
    assert [t.name for t in queue.tools(run)] == [
        "list_waiting_claims",
        "write_todos",
        "work_claim",
        "finish_run",
    ]


def test_the_command_line_follows_a_run(client, monkeypatch, capsys):
    def finish_on_poll(seconds):
        client.post("/api/runs/1/finish", json={"summary": "One claim decided."})

    monkeypatch.setattr("agent.__main__.time.sleep", finish_on_poll)
    main(["--cap", "1"])
    client.post("/api/runs/1/todos", json={"todos": []})
    assert capsys.readouterr().out == "Run 1 finished: One claim decided.\n"


def test_the_command_line_shows_todos_and_one_claim(client, monkeypatch, capsys):
    def tick(seconds):
        client.post(
            "/api/runs/1/todos",
            json={
                "todos": [
                    {"claim_id": "CLM-1001", "content": "Delay", "status": "done"}
                ]
            },
        )
        client.post("/api/runs/1/fail", json={"problem": "Stopped."})

    monkeypatch.setattr("agent.__main__.time.sleep", tick)
    main(["CLM-1001"])
    assert capsys.readouterr().out == (
        "CLM-1001: done  Delay\nRun 1 failed: Stopped.\n"
    )
    assert run(client, 1)["claim_id"] == "CLM-1001"


def test_the_command_line_shows_a_refusal(client, capsys):
    start(client, 1)
    main(["--cap", "1"])
    assert capsys.readouterr().out == (
        "Refused: A run is already going; wait for it to finish\n"
    )


@pytest.mark.parametrize("argv", [[], ["CLM-1001", "--cap", "2"]])
def test_the_command_line_needs_a_claim_or_a_cap(argv):
    with pytest.raises(SystemExit):
        main(argv)
