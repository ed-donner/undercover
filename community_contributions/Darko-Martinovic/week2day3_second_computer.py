"""The second computer for the Week 2 Day 3 stretch challenge.

It shares nothing with the notebook but the repo and DATABASE_URL. It builds the same graph,
finds a claim's paused thread in Supabase and resumes it with a handler's approval.

    uv run python week2day3_second_computer.py <thread id> <handler>
"""

import json
import operator
import os
import sys
from pathlib import Path
from typing import Annotated, Literal, TypedDict

import psycopg
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.types import Command, interrupt
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "labs"))
from week2day1_payout import Benefit, Line, Payout, work_out_payout  # noqa: E402

load_dotenv(ROOT / ".env", override=True)
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DATA = ROOT / "data"


def load(name):
    """Read one of UnderCover's JSON files."""
    return json.loads((DATA / name).read_text(encoding="utf-8"))


policies = {policy["policy_id"]: policy for policy in load("policies.json")}
policy_wording = (DATA / "policy_wording.md").read_text(encoding="utf-8")
APPROVAL_LIMIT = load("company.json")["payout_approval_limit"]
MAX_REJECTIONS = 2

INSTRUCTIONS = """You are a claims handler at UnderCover Travel Insurance.
Decide the claim you are given, using the policy wording below and the customer's policy record.

Choose one decision:
- approve: the wording covers the claim and the required documents are attached. Work out the payout using section 10.
- decline: the wording does not cover the claim.
- refer: a colleague needs to look at it, because a required document is missing, or the story and the documents disagree, or the wording does not settle the question.

Use the payout tool to work out the payout on an approved claim. When you have decided, give your decision, the payout and your reasons.
"""


class ClaimState(TypedDict):
    """What the graph keeps for one claim."""

    messages: Annotated[list, add_messages]
    claim_id: str
    decision: str
    payout: float
    rationale: str
    approved_by: str
    rejections: int
    notes: Annotated[list, operator.add]


class ClaimDecision(BaseModel):
    """A claims handler's decision on one claim."""

    rationale: str = Field(description="2-3 sentences to explain the decision along with the relevant section of the policy")
    decision: Literal["approve", "decline", "refer"]
    payout: float = Field(description="The amount to pay in US dollars, or 0 for a decline or a referral")


@tool(parse_docstring=True)
def calculate_payout(policy_id: str, benefit: Benefit, lines: list[Line], paid_by_others: float = 0.0) -> Payout:
    """Work out the payout on an approved claim with UnderCover's payout rules.

    Args:
        policy_id: The customer's policy id
        benefit: The benefit the claim is paid under
        lines: The covered items and expenses, one for each line of the claim, with any excluded ones left out. A pair or a set counts as one item
        paid_by_others: Anything a carrier, hotel or other party has paid or refunded for the same loss

    Returns:
        The calculation, the payout and whether it needs sign-off
    """
    return work_out_payout(policies[policy_id], benefit, lines, paid_by_others)


luna = ChatOpenAI(model="openai/gpt-6-luna", base_url=OPENROUTER_BASE_URL, api_key=os.getenv("OPENROUTER_API_KEY"), reasoning_effort="low", timeout=120, max_retries=5)
model_with_tools = luna.bind_tools([calculate_payout])
decider = luna.with_structured_output(ClaimDecision)
system_message = SystemMessage(f"{INSTRUCTIONS}\n{policy_wording}\n")
connection = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True, prepare_threshold=0, row_factory=dict_row, options="-c search_path=lab")


def agent(state: ClaimState):
    """Call the model with the conversation so far."""
    return {"messages": [model_with_tools.invoke([system_message, *state["messages"]])]}


def decide(state: ClaimState):
    """Turn the agent's work into a decision."""
    result = decider.invoke([system_message, *state["messages"], HumanMessage("Record your decision on this claim.")])
    return {"decision": result.decision, "payout": result.payout, "rationale": result.rationale}


def approval(state: ClaimState):
    """Wait for a handler to approve or reject the payout."""
    print(f"{state['claim_id']} needs a handler to approve ${state['payout']:,.2f}")
    answer = interrupt({"claim_id": state["claim_id"], "decision": state["decision"], "payout": state["payout"], "rationale": state["rationale"]})
    if answer["approved"]:
        return {"approved_by": answer["handler"]}
    note = f"{answer['handler']} rejected the payout of ${state['payout']:,.2f}: {answer['note']}"
    rejections = state.get("rejections", 0) + 1
    update = {"messages": [HumanMessage(note)], "rejections": rejections, "notes": [note]}
    if rejections >= MAX_REJECTIONS:
        update |= {"decision": "refer", "payout": 0.0, "rationale": f"Referred after {rejections} rejections by a handler"}
    return update


def pay(state: ClaimState):
    """Pay the claim, unless it has been paid already."""
    cursor = connection.execute(
        "INSERT INTO challenge_payments (claim_id, amount, approved_by) VALUES (%s, %s, %s) ON CONFLICT (claim_id) DO NOTHING",
        (state["claim_id"], state["payout"], state.get("approved_by")),
    )
    if cursor.rowcount:
        print(f"Paid {state['claim_id']} ${state['payout']:,.2f}")
    else:
        print(f"{state['claim_id']} was already paid")


def after_agent(state: ClaimState):
    """Run the tools the model asked for, or move on to the decision."""
    if state["messages"][-1].tool_calls:
        return "tools"
    return "decide"


def after_decide(state: ClaimState):
    """Send any decision a handler rejected before back to a handler; otherwise pay an approval, after a handler's approval if it's over the limit."""
    if state.get("rejections"):
        return "approval"
    if state["decision"] != "approve":
        return END
    if state["payout"] > APPROVAL_LIMIT:
        return "approval"
    return "pay"


def after_approval(state: ClaimState):
    """Pay an approved payout, end a confirmed decline or referral, send a rejection back to the agent, or stop at the limit."""
    if state.get("approved_by"):
        return "pay" if state["decision"] == "approve" else END
    if state.get("rejections", 0) >= MAX_REJECTIONS:
        return END
    return "agent"


builder = StateGraph(ClaimState)
builder.add_node("agent", agent)
builder.add_node("tools", ToolNode([calculate_payout]))
builder.add_node("decide", decide)
builder.add_node("approval", approval)
builder.add_node("pay", pay)

builder.add_edge(START, "agent")
builder.add_conditional_edges("agent", after_agent, ["tools", "decide"])
builder.add_edge("tools", "agent")
builder.add_conditional_edges("decide", after_decide, ["approval", "pay", END])
builder.add_conditional_edges("approval", after_approval, ["pay", "agent", END])
builder.add_edge("pay", END)

graph = builder.compile(checkpointer=PostgresSaver(connection))


if __name__ == "__main__":
    thread_id, handler = sys.argv[1:3]
    config = {"configurable": {"thread_id": thread_id}}
    state = graph.get_state(config)
    if state.next != ("approval",):
        sys.exit(f"{thread_id} isn't waiting for a handler's approval")
    print(f"Process {os.getpid()} found {thread_id} waiting at {state.next}: {state.interrupts[0].value['payout']:,.2f}")
    graph.invoke(Command(resume={"handler": handler, "approved": True}), config, durability="sync")
