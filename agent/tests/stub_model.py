"""A scripted chat model for tests: it plays the queue runner and the claim subagent."""

import json
import re
from typing import Any
from uuid import uuid4

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult


def tool_call(name: str, args: dict) -> AIMessage:
    return AIMessage(
        content="", tool_calls=[{"name": name, "args": args, "id": uuid4().hex}]
    )


class StubModel(BaseChatModel):
    """Behaves like a small model that follows the instructions.

    The dicts count how many times to misbehave, per claim id (or "runner").
    """

    tools: list[str] = []
    errors: dict[str, int] = {}
    lazy: dict[str, int] = {}
    payouts: dict[str, float] = {}
    repeat_decision: bool = False
    stop_early: bool = False

    @property
    def _llm_type(self) -> str:
        return "stub"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "StubModel":
        return self.model_copy(update={"tools": [t.name for t in tools]})

    def _generate(self, messages: list[BaseMessage], *args: Any, **kwargs: Any):
        reply = (
            self.runner(messages)
            if "work_claim" in self.tools
            else self.claim(messages)
        )
        return ChatResult(generations=[ChatGeneration(message=reply)])

    def misbehave(self, kind: dict[str, int], key: str) -> bool:
        if kind.get(key, 0) > 0:
            kind[key] -= 1
            return True
        return False

    def runner(self, messages: list[BaseMessage]) -> AIMessage:
        if self.misbehave(self.errors, "runner"):
            raise ConnectionError("provider error")
        start = max(i for i, m in enumerate(messages) if isinstance(m, HumanMessage))
        segment = messages[start:]
        calls = [c for m in segment if isinstance(m, AIMessage) for c in m.tool_calls]
        names = [c["name"] for c in calls]
        result = str(segment[-1].content)
        nudged = re.findall(r"CLM-\d+", str(segment[0].content))
        if not calls:
            return self.begin(nudged)
        if names[-1] == "list_waiting_claims":
            return tool_call("write_todos", {"items": self.items(result)})
        if names[-1] == "check_missed":
            return self.finish(json.loads(result)["missed"])
        planned = nudged or [
            i["claim_id"]
            for c in calls
            if c["name"] == "write_todos"
            for i in c["args"]["items"]
        ]
        worked = [c["args"]["claim_id"] for c in calls if c["name"] == "work_claim"]
        pending = [i for i in planned if i not in worked]
        if pending:
            return tool_call("work_claim", {"claim_id": pending[0]})
        return tool_call("check_missed", {})

    def begin(self, nudged: list[str]) -> AIMessage:
        if nudged:
            return tool_call("work_claim", {"claim_id": nudged[0]})
        return tool_call("list_waiting_claims", {})

    def finish(self, missed: list[str]) -> AIMessage:
        if missed and not self.stop_early:
            return tool_call("work_claim", {"claim_id": missed[0]})
        return AIMessage(content="Summary for handlers: run complete.")

    def items(self, waiting: str) -> list[dict]:
        info = json.loads(waiting)
        ids = [c["claim_id"] for c in info["waiting"]][: info["cap"]]
        ids = ids[:1] if self.stop_early else ids
        return [{"claim_id": i, "text": f"Work {i}", "state": "todo"} for i in ids]

    def claim(self, messages: list[BaseMessage]) -> AIMessage:
        first = next(m for m in messages if isinstance(m, HumanMessage))
        claim_id = re.search(r"CLM-\d+", str(first.content))
        assert claim_id
        claim_id = claim_id.group()
        if self.misbehave(self.errors, claim_id):
            raise TimeoutError("provider timeout")
        done = sum(isinstance(m, ToolMessage) for m in messages)
        payout = self.payouts.get(claim_id, 100.0)
        decide = tool_call(
            "decide",
            {
                "decision": "approve" if payout else "decline",
                "payout": payout,
                "section": "3",
                "reason": "Covered under the wording.",
            },
        )
        script = [
            tool_call("get_claim", {}),
            tool_call(
                "search_sections", {"document": "manual", "query": "wild animals"}
            ),
            tool_call("read_section", {"document": "manual", "number": 4}),
            tool_call("read_section", {"document": "wording", "number": 3}),
        ]
        if not self.misbehave(self.lazy, claim_id):
            script.append(decide)
            if self.repeat_decision:
                script.append(decide)
            if payout:
                script.append(tool_call("pay", {"amount": payout}))
                if self.repeat_decision:
                    script.append(tool_call("pay", {"amount": payout}))
        if done < len(script):
            return script[done]
        return AIMessage(content=f"{claim_id}: done")
