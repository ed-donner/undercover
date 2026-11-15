"""A chat model that answers from a script instead of calling a provider."""

import json
import re
from collections.abc import Callable, Generator
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

Responder = Callable[[list[BaseMessage]], AIMessage]


class StubModel(BaseChatModel):
    """A chat model whose replies come from a function of the conversation."""

    responder: Responder

    @property
    def _llm_type(self) -> str:
        return "stub"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "StubModel":  # noqa: ANN401, ARG002
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> ChatResult:
        return ChatResult(
            generations=[ChatGeneration(message=self.responder(messages))]
        )


def call(name: str, args: dict[str, Any], call_id: str) -> AIMessage:
    """Build a reply that calls one tool."""
    return AIMessage(
        content="", tool_calls=[{"name": name, "args": args, "id": call_id}]
    )


def tool_results(messages: list[BaseMessage]) -> list[str]:
    """Return the text of every tool result so far."""
    return [str(m.content) for m in messages if isinstance(m, ToolMessage)]


def first_user_text(messages: list[BaseMessage]) -> str:
    """Return the first user message."""
    return next(str(m.content) for m in messages if isinstance(m, HumanMessage))


def claim_script(
    claim_id: str, decision: str = "decline", payout: float = 0
) -> Responder:
    """Script a claim agent: read, look up, read two sections, decide and pay."""

    def respond(messages: list[BaseMessage]) -> AIMessage:
        step = len(tool_results(messages))
        approve = decision == "approve" and payout <= 1000  # noqa: PLR2004
        script = [
            ("get_claim", {}),
            ("look_up_policy", {}),
            ("look_up_history", {}),
            ("read_section", {"document": "policy_wording", "number": 3}),
            ("read_section", {"document": "claims_manual", "number": 9}),
            (
                "decide",
                {
                    "decision": decision,
                    "payout": payout,
                    "policy_section": "Wording section 3",
                    "reason": "Stub reason.",
                },
            ),
            *([("pay", {"amount": payout})] if approve else []),
        ]
        if step < len(script):
            name, args = script[step]
            return call(name, args, f"{claim_id}-{step}")
        return AIMessage(content=f"{claim_id}: {decision}")

    return respond


def nudged(messages: list[BaseMessage], at: int) -> AIMessage:
    """Work the claims a nudge names, then finish."""
    ids = re.findall(r"CLM-\d+", str(messages[at].content))
    done = len(tool_results(messages[at:]))
    if done < len(ids):
        return call("work_claim", {"claim_id": ids[done]}, f"missed-{done}")
    return AIMessage(content="Summary: the run is finished.")


Step = tuple[str, dict[str, Any]]


def first_pass(
    skip: frozenset[str], retry: frozenset[str]
) -> Generator[Step, str, None]:
    """Yield each tool call of the queue agent's first pass and take its result back."""
    listed = yield ("list_waiting_claims", {})
    ids = [c["claim_id"] for c in json.loads(listed) if c["claim_id"] not in skip]
    todos = {i: "todo" for i in ids}

    def plan() -> dict[str, Any]:
        return {"todos": [{"text": t, "status": s} for t, s in todos.items()]}

    yield ("write_todos", plan())
    queue, retried = list(ids), set()
    for claim in queue:
        todos[claim] = "in_progress"
        yield ("write_todos", plan())
        line = yield ("work_claim", {"claim_id": claim})
        if "back in the queue" in line and claim in retry - retried:
            retried.add(claim)
            queue.append(claim)
            todos[claim] = "todo"
        else:
            todos[claim] = "for_handler" if "left for a handler" in line else "done"
        yield ("write_todos", plan())


def next_step(
    results: list[str], skip: frozenset[str], retry: frozenset[str]
) -> Step | None:
    """Replay the first pass against the results so far and return its next call."""
    steps = first_pass(skip, retry)
    step = next(steps)
    for result in results:
        try:
            step = steps.send(result)
        except StopIteration:
            return None
    return step


def queue_script(
    claim_script_for: Callable[[str], Responder],
    skip: frozenset[str] = frozenset(),
    retry: frozenset[str] = frozenset(),
) -> Responder:
    """Script the queue agent and, by the first message, the claim agent.

    The queue agent lists, plans, works each claim with the to-do list kept up to
    date, and ends with a summary. Claims in skip are left out of its first pass,
    to test the missed-claim check. Claims in retry are worked again once after a
    failure.
    """

    def respond(messages: list[BaseMessage]) -> AIMessage:
        user = first_user_text(messages)
        if user.startswith("Claim "):
            return claim_script_for(user.removeprefix("Claim "))(messages)
        humans = [i for i, m in enumerate(messages) if isinstance(m, HumanMessage)]
        if len(humans) > 1:
            return nudged(messages, humans[-1])
        step = next_step(tool_results(messages), skip, retry)
        if step is None:
            return AIMessage(content="Summary: the run is finished.")
        return call(step[0], step[1], f"c{len(tool_results(messages))}")

    return respond
