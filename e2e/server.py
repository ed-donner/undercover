"""Isolated end-to-end server; never used by the development application."""

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event

import uvicorn
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from agent.main import run
from backend.main import create_app


class StubModel(GenericFakeChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


def call(name: str, args: dict) -> AIMessage:
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
        call("read_wording", {}),
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
            },
        ),
    ]
    if outcome == "approve":
        messages.append(call("request_payment", {"amount": payout}))
    messages.append(AIMessage(content="Scripted decision recorded."))
    return StubModel(messages=iter(messages))


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
        return run(claim_id, thread_id, llm=scripted_model(claim_id))

    with TemporaryDirectory(prefix="undercover-e2e-") as directory:
        app = create_app(Path(directory) / "claims.db", runner=runner)

        @app.post("/__test__/reset", operation_id="test_reset")
        def reset() -> dict[str, str]:
            """Reset only this test process's temporary database."""
            released.set()
            app.state.executor.shutdown(wait=True)
            with app.state.store.connect() as connection:
                connection.executescript("""
                    BEGIN IMMEDIATE;
                    DELETE FROM events;
                    DELETE FROM payments;
                    DELETE FROM sign_offs;
                    DELETE FROM decisions;
                    DELETE FROM runs;
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
