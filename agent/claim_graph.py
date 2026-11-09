"""The claim agent's graph: its nodes joined by edges, and the checkpointer.

START -> agent <-> tools; agent -> settle; settle -> agent (no decision yet),
END (decline or referral), approval -> pay (over the limit) or pay.
"""

from functools import partial
from typing import Literal

from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode

from agent import claim_nodes
from agent.api import ApiRefusal
from agent.claim_state import ClaimState
from agent.contexts import ClaimContext
from agent.tools import CLAIM_TOOLS


def after_agent(state: ClaimState) -> Literal["tools", "settle"]:
    """Run the tools the model asked for, or move on to the decision."""
    return "tools" if state["messages"][-1].tool_calls else "settle"


def after_settle(state: ClaimState) -> str:
    """Send the claim back to the agent, or on to a sign-off or a payment, or end it."""
    if not state["decision"]:
        return "agent"
    if state["decision"] != "approve":
        return END
    return "approval" if state["needs_sign_off"] else "pay"


def build_graph(
    checkpointer: BaseCheckpointSaver, model: BaseChatModel, instructions: str
) -> CompiledStateGraph[ClaimState, ClaimContext, ClaimState, ClaimState]:
    """Build the claim graph on a checkpointer."""
    builder = StateGraph(ClaimState, context_schema=ClaimContext)
    builder.add_node(
        "agent",
        partial(
            claim_nodes.agent,
            model=model.bind_tools(CLAIM_TOOLS),
            instructions=instructions,
        ),
    )
    builder.add_node("tools", ToolNode(CLAIM_TOOLS, handle_tool_errors=ApiRefusal))
    builder.add_node("settle", claim_nodes.settle)
    builder.add_node("approval", claim_nodes.approval)
    builder.add_node("pay", claim_nodes.pay)

    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", after_agent, ["tools", "settle"])
    builder.add_edge("tools", "agent")
    builder.add_conditional_edges(
        "settle", after_settle, ["agent", "approval", "pay", END]
    )
    builder.add_edge("approval", "pay")
    builder.add_edge("pay", END)
    return builder.compile(checkpointer=checkpointer)
