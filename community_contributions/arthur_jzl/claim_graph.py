"""The Week 2 Day 3 claims graph, with a handler who can approve or reject a payout.

The notebook and approve_claim.py both build the graph from here, so a claim paused in one
can be approved or rejected from the other, or from another computer with the same DATABASE_URL.
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
SCHEMA = "lab_reject"
MAX_REJECTIONS = 2

DATA = ROOT / "data"


def load(name):
    """Read one of UnderCover's JSON files."""
    return json.loads((DATA / name).read_text(encoding="utf-8"))


claims = {claim["claim_id"]: claim for claim in load("claims.json")}
policies = {policy["policy_id"]: policy for policy in load("policies.json")}
policy_wording = (DATA / "policy_wording.md").read_text(encoding="utf-8")
APPROVAL_LIMIT = load("company.json")["payout_approval_limit"]

INSTRUCTIONS = """You are a claims handler at UnderCover Travel Insurance.
Decide the claim you are given, using the policy wording below and the customer's policy record.

Choose one decision:
- approve: the wording covers the claim and the required documents are attached. Work out the payout using section 10.
- decline: the wording does not cover the claim.
- refer: a colleague needs to look at it, because a required document is missing, or the story and the documents disagree, or the wording does not settle the question.

Use the payout tool to work out the payout on an approved claim. When you have decided, give your decision, the payout and your reasons.
"""


def make_user_prompt(claim):
    """The customer's policy record and the claim, as JSON."""
    policy = policies[claim["policy_id"]]
    return f"""# Policy record

{json.dumps(policy, indent=2)}

# Claim

{json.dumps(claim, indent=2)}
"""


@tool(parse_docstring=True)
def calculate_payout(
    policy_id: str, benefit: Benefit, lines: list[Line], paid_by_others: float = 0.0
) -> Payout:
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


class ClaimDecision(BaseModel):
    """A claims handler's decision on one claim."""

    rationale: str = Field(
        description="2-3 sentences to explain the decision along with the relevant section of the policy"
    )
    decision: Literal["approve", "decline", "refer"]
    payout: float = Field(
        description="The amount to pay in US dollars, or 0 for a decline or a referral"
    )


class ClaimState(TypedDict):
    """What the graph keeps for one claim."""

    messages: Annotated[list, add_messages]
    claim_id: str
    decision: str
    payout: float
    rationale: str
    calculation: list
    approved_by: str
    reviews: Annotated[list, operator.add]


system_message = SystemMessage(f"{INSTRUCTIONS}\n{policy_wording}\n")


def latest_calculation(messages):
    """The steps of the payout tool's most recent calculation, or an empty list."""
    for message in reversed(messages):
        if message.type == "tool" and message.name == "calculate_payout":
            try:
                return json.loads(message.text)["calculation"]
            except (json.JSONDecodeError, KeyError, TypeError):
                return []
    return []


def approval(state: ClaimState):
    """Wait for a handler to approve or reject the decision, then pay it, send it back to the agent, or refer it."""
    reviews = state.get("reviews", [])
    print(
        f"{state['claim_id']} needs a handler to review {state['decision']} ${state['payout']:,.2f} (round {len(reviews) + 1})"
    )
    answer = interrupt(
        {
            "claim_id": state["claim_id"],
            "decision": state["decision"],
            "payout": state["payout"],
            "rationale": state["rationale"],
            "calculation": state.get("calculation", []),
            "round": len(reviews) + 1,
        }
    )

    handler = answer.get("handler") or "A handler"
    approved = answer.get("approved") is True
    note = (answer.get("note") or "").strip()
    review = {
        "handler": handler,
        "approved": approved,
        "note": note,
        "decision": state["decision"],
        "payout": state["payout"],
    }

    if approved:
        if state["decision"] != "approve":
            return Command(update={"reviews": [review]}, goto=END)
        return Command(update={"approved_by": handler, "reviews": [review]}, goto="pay")

    rejections = sum(not past["approved"] for past in reviews) + 1
    if rejections >= MAX_REJECTIONS:
        rationale = f"Referred to a handler after {rejections} rejected decisions. The last note, from {handler}: {note or 'none given'}"
        return Command(
            update={
                "reviews": [review],
                "decision": "refer",
                "payout": 0.0,
                "rationale": rationale,
            },
            goto=END,
        )

    message = HumanMessage(
        f"{handler}, a claims handler, rejected your decision on {state['claim_id']}: {state['decision']} ${state['payout']:,.2f}.\n"
        f"Their note: {note or 'none given'}\n"
        "Look at the claim again with the note in mind. If you approve it, work out the payout again with the payout tool. "
        "Then give your decision, the payout and your reasons."
    )
    return Command(update={"messages": [message], "reviews": [review]}, goto="agent")


def after_agent(state: ClaimState):
    """Run the tools the model asked for, or move on to the decision."""
    if state["messages"][-1].tool_calls:
        return "tools"
    return "decide"


def after_decide(state: ClaimState):
    """Send a payout over the limit, or any decision after a rejection, to a handler. Pay the rest of the approvals."""
    if state.get("reviews") and state["decision"] != "refer":
        return "approval"
    if state["decision"] != "approve":
        return END
    if state["payout"] > APPROVAL_LIMIT:
        return "approval"
    return "pay"


def connect():
    """A connection to Supabase, with this contribution's tables in a schema of their own."""
    connection = psycopg.connect(
        os.getenv("DATABASE_URL"),
        autocommit=True,
        prepare_threshold=0,
        row_factory=dict_row,
        options=f"-c search_path={SCHEMA}",
    )
    connection.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
    connection.execute("""
    CREATE TABLE IF NOT EXISTS payments (
        claim_id TEXT PRIMARY KEY,
        amount NUMERIC NOT NULL,
        approved_by TEXT,
        review_rounds INTEGER NOT NULL DEFAULT 0,
        paid_at TIMESTAMPTZ DEFAULT now()
    )
    """)
    return connection


def build_graph(connection, reasoning_effort="low"):
    """The claims graph, with its checkpoints saved in Supabase, running Luna at the reasoning effort given."""
    luna = ChatOpenAI(
        model="openai/gpt-6-luna",
        base_url=OPENROUTER_BASE_URL,
        api_key=os.getenv("OPENROUTER_API_KEY"),
        reasoning_effort=reasoning_effort,
        timeout=120,
        max_retries=5,
    )
    model_with_tools = luna.bind_tools([calculate_payout])
    decider = luna.with_structured_output(ClaimDecision)

    def agent(state: ClaimState):
        """Call the model with the conversation so far."""
        return {
            "messages": [model_with_tools.invoke([system_message, *state["messages"]])]
        }

    def decide(state: ClaimState):
        """Turn the agent's work into a decision, with the calculation behind its payout."""
        result = decider.invoke(
            [
                system_message,
                *state["messages"],
                HumanMessage("Record your decision on this claim."),
            ]
        )
        calculation = (
            latest_calculation(state["messages"])
            if result.decision == "approve"
            else []
        )
        return {
            "decision": result.decision,
            "payout": result.payout,
            "rationale": result.rationale,
            "calculation": calculation,
        }

    def pay(state: ClaimState):
        """Pay the claim, unless it has been paid already."""
        cursor = connection.execute(
            "INSERT INTO payments (claim_id, amount, approved_by, review_rounds) VALUES (%s, %s, %s, %s) ON CONFLICT (claim_id) DO NOTHING",
            (
                state["claim_id"],
                state["payout"],
                state.get("approved_by"),
                len(state.get("reviews", [])),
            ),
        )
        if cursor.rowcount:
            print(f"Paid {state['claim_id']} ${state['payout']:,.2f}")
        else:
            print(f"{state['claim_id']} was already paid")

    checkpointer = PostgresSaver(connection)
    checkpointer.setup()

    builder = StateGraph(ClaimState)
    builder.add_node("agent", agent)
    builder.add_node("tools", ToolNode([calculate_payout]))
    builder.add_node("decide", decide)
    builder.add_node("approval", approval, destinations=("pay", "agent", END))
    builder.add_node("pay", pay)

    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", after_agent, ["tools", "decide"])
    builder.add_edge("tools", "agent")
    builder.add_conditional_edges("decide", after_decide, ["approval", "pay", END])
    builder.add_edge("pay", END)

    return builder.compile(checkpointer=checkpointer)


def start_fresh(connection, graph, claim_id):
    """Delete a claim's saved thread and its payment."""
    graph.checkpointer.delete_thread(claim_id)
    connection.execute("DELETE FROM payments WHERE claim_id = %s", (claim_id,))


def start_claim(graph, claim_id):
    """Run a claim from the start until it pauses for a handler or finishes."""
    config = {"configurable": {"thread_id": claim_id}}
    claim = {
        "messages": [HumanMessage(make_user_prompt(claims[claim_id]))],
        "claim_id": claim_id,
    }
    return graph.invoke(claim, config, durability="sync")


def review(graph, claim_id, handler, approved, note=""):
    """Resume a paused claim with a handler's answer, and run it until it pauses again or finishes."""
    config = {"configurable": {"thread_id": claim_id}}
    return graph.invoke(
        Command(resume={"handler": handler, "approved": approved, "note": note}),
        config,
        durability="sync",
    )


def waiting_for_review(connection, graph):
    """What each claim paused for a handler is waiting on, read from Supabase."""
    thread_ids = [
        row["thread_id"]
        for row in connection.execute(
            "SELECT DISTINCT thread_id FROM checkpoints ORDER BY thread_id"
        ).fetchall()
    ]
    waiting = []
    for thread_id in thread_ids:
        state = graph.get_state({"configurable": {"thread_id": thread_id}})
        if state.interrupts:
            waiting.append(state.interrupts[0].value)
    return waiting
