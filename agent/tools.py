"""The tools of the claim subagent, and the recorder of its steps."""

import json
from collections.abc import Callable
from typing import Any, Literal
from urllib.parse import quote

from langchain.agents.middleware import AgentMiddleware, wrap_tool_call
from langchain.agents.middleware.types import ToolCallRequest
from langchain_core.tools import BaseTool, tool

from agent.client import call

Document = Literal["manual", "wording"]


def text(value: Any) -> str:
    """Show a backend answer to the model."""
    return json.dumps(value)


def claim_tools(claim_id: str) -> list[BaseTool]:
    """Return the tools for working one claim; they cannot touch another claim."""

    @tool
    def get_claim() -> str:
        """Get the claim: the story, the items claimed and the documents."""
        claim = call("GET", f"/api/claims/{claim_id}")
        for key in ("steps", "reads", "decision", "payment", "signed_off_by"):
            claim.pop(key, None)
        return text(claim)

    @tool
    def get_policy() -> str:
        """Get the claim's policy: plan, add-ons, dates, travelers and plan terms."""
        claim = call("GET", f"/api/claims/{claim_id}")
        return text(call("GET", f"/api/policies/{claim['policy_id']}"))

    @tool
    def get_claim_history() -> str:
        """Get the customer's earlier claims, with the date each was filed."""
        claim = call("GET", f"/api/claims/{claim_id}")
        return text(call("GET", f"/api/customers/{claim['customer_id']}/history"))

    @tool
    def list_sections(document: Document) -> str:
        """List the section numbers and titles of the manual or the wording."""
        return text(call("GET", f"/api/sections/{document}"))

    @tool
    def search_sections(document: Document, query: str) -> str:
        """Find the sections of the manual or the wording that match some words."""
        return text(
            call("GET", f"/api/sections/{document}/search?query={quote(query)}")
        )

    @tool
    def read_section(document: Document, number: int) -> str:
        """Read one section of the manual or the wording in full."""
        body = {"document": document, "number": number}
        return text(call("POST", f"/api/claims/{claim_id}/reads", body))

    @tool
    def decide(
        decision: Literal["approve", "decline", "refer"],
        payout: float,
        section: str,
        reason: str,
    ) -> str:
        """Record the decision: payout (0 unless approved), section and reason."""
        body = {
            "decision": decision,
            "payout": payout,
            "section": section,
            "reason": reason,
        }
        return text(call("POST", f"/api/claims/{claim_id}/decision", body))

    @tool
    def pay(amount: float) -> str:
        """Pay an approved claim whose payout is $1,000 or less."""
        return text(call("POST", f"/api/claims/{claim_id}/payment", {"amount": amount}))

    return [
        get_claim,
        get_policy,
        get_claim_history,
        list_sections,
        search_sections,
        read_section,
        decide,
        pay,
    ]


def step_recorder(claim_id: str) -> AgentMiddleware:
    """Return middleware that records every tool call on the claim."""

    def record(request: ToolCallRequest, outcome: str) -> None:
        name, args = request.tool_call["name"], json.dumps(request.tool_call["args"])
        call(
            "POST",
            f"/api/claims/{claim_id}/steps",
            {"tool": name, "summary": f"{args} -> {outcome}"},
        )

    @wrap_tool_call
    def recorder(request: ToolCallRequest, handler: Callable) -> Any:
        try:
            result = handler(request)
        except Exception as error:
            record(request, f"error: {error}")
            raise
        record(request, str(getattr(result, "content", result)))
        return result

    return recorder
