"""Isolated end-to-end server; never used by the development application."""

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event

import uvicorn
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from agent.main import backend, run
from agent.queue import run_queue
from backend.main import create_app


class StubModel(GenericFakeChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


def call(name: str, args: dict) -> AIMessage:
    if name == "record_decision":
        args = {"decision": args}
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": name}])


def scripted_model(claim_id: str) -> StubModel:
    # Synthetic workflow fixtures, not expected decisions for the business queue.
    outcome, payout = {
        "CLM-1001": ("approve", "420"),
        "CLM-1002": ("decline", "0"),
        "CLM-1003": ("approve", "1200"),
        "CLM-1004": ("refer", "0"),
    }.get(claim_id, ("refer", "0"))
    messages = [
        call("read_context", {}),
        call("list_sections", {}),
        call("read_section", {"document_id": "wording", "section": 3}),
        call("read_section", {"document_id": "wording", "section": 10}),
        call("read_section", {"document_id": "manual", "section": 4}),
        call("read_section", {"document_id": "manual", "section": 9}),
        call(
            "record_decision",
            {
                "outcome": outcome,
                "payout": payout,
                "calculation": f"Synthetic workflow fixture: payout ${payout}.",
                "explanation": (
                    "This scripted decision tests the pilot workflow. "
                    "It does not measure policy accuracy."
                ),
                "policy_sections": [3, 10],
                "manual_version": "2026.2",
                "manual_sections": [4, 9],
            },
        ),
    ]
    if outcome == "approve":
        messages.append(call("request_payment", {"amount": payout}))
    messages.append(AIMessage(content="Scripted decision recorded."))
    return StubModel(messages=iter(messages))


def supervisor_model(run_id: str) -> StubModel:
    path = f"/api/agent-runs/{run_id}"

    def messages():
        with backend() as client:
            yield call("read_queue", {})
            state = client.get(path).json()
            selected = list(reversed(state["scope"][: state["max_claims"]]))
            initial = selected[:-1] if len(selected) > 1 else selected
            yield call(
                "write_todos",
                {"tasks": [{"claim_id": key, "state": "todo"} for key in initial]},
            )
            for claim_id in initial:
                yield from work(client, claim_id)
            yield call("check_completion", {})
            if initial != selected:
                state = client.get(path).json()
                tasks = [
                    {"claim_id": task["claim_id"], "state": task["state"]}
                    for task in state["tasks"]
                ]
                tasks.append({"claim_id": selected[-1], "state": "todo"})
                yield call("write_todos", {"tasks": tasks})
                yield from work(client, selected[-1])
                yield call("check_completion", {})
            yield call("finish_run", {})

    return StubModel(messages=messages())


def work(client, claim_id):
    yield call("delegate_claim", {"claim_id": claim_id})
    yield call("read_queue", {})
    claim = client.get(f"/api/claims/{claim_id}").json()
    if claim["decision"] is None and not claim["needs_handler"]:
        yield call("delegate_claim", {"claim_id": claim_id})
        yield call("read_queue", {})


def main() -> None:
    os.environ["OPENROUTER_API_KEY"] = ""
    os.environ["BACKEND_URL"] = "http://127.0.0.1:8011"
    released = Event()
    attempts: dict[str, int] = {}

    def runner(claim_id: str, thread_id: str) -> str:
        if not released.wait(10):
            raise RuntimeError("Test did not release the controlled agent")
        attempts[claim_id] = attempts.get(claim_id, 0) + 1
        if claim_id == "CLM-1005" and attempts[claim_id] == 1:
            raise RuntimeError("Synthetic first-run failure")
        if claim_id == "CLM-1006":
            raise RuntimeError("Synthetic persistent failure")
        return run(claim_id, thread_id, llm=scripted_model(claim_id))

    def queue_runner(run_id: str, thread_id: str) -> str:
        return run_queue(run_id, thread_id, llm=supervisor_model(run_id))

    with TemporaryDirectory(prefix="undercover-e2e-") as directory:
        app = create_app(
            Path(directory) / "claims.db", runner=runner, queue_runner=queue_runner
        )

        @app.post("/__test__/reset", operation_id="test_reset")
        def reset() -> dict[str, str]:
            """Reset only this test process's temporary database."""
            released.set()
            app.state.executor.shutdown(wait=True)
            with app.state.store.connect() as connection:
                connection.executescript("""
                    BEGIN IMMEDIATE;
                    DELETE FROM document_reads;
                    DELETE FROM events;
                    DELETE FROM payments;
                    DELETE FROM sign_offs;
                    DELETE FROM decisions;
                    DELETE FROM runs;
                    DELETE FROM todos;
                    DELETE FROM agent_runs;
                    DELETE FROM claims;
                    DELETE FROM records;
                    COMMIT;
                """)
            app.state.store.initialize()
            attempts.clear()
            released.clear()
            app.state.executor = ThreadPoolExecutor(max_workers=4)
            return {"status": "reset"}

        @app.post("/__test__/release", operation_id="test_release")
        def release() -> dict[str, str]:
            """Release the controlled scripted agent in this test process."""
            released.set()
            return {"status": "released"}

        uvicorn.run(app, host="127.0.0.1", port=8011)


if __name__ == "__main__":
    main()
