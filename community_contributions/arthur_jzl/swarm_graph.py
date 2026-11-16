"""The Week 2 Day 4 dispatcher, with a score_run node that scores the whole run.

The notebook builds the dispatcher from here, and so does a separate process that the notebook
kills part way through a run, to test what LangGraph saves in Supabase and what it works again.

uv run community_contributions/arthur_jzl/swarm_graph.py swarm-sync --durability sync
    Runs the swarm on the thread swarm-sync, 5 claims at once, saving checkpoints in Supabase.
uv run community_contributions/arthur_jzl/swarm_graph.py swarm-gate --at-once 5
    The same, with the claims capped by a gate in the node.
"""

import argparse
import json
import operator
import os
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal, TypedDict

import pandas as pd
import psycopg
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy, Send
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "labs"))
from week2day1_payout import Benefit, Line, Payout, work_out_payout  # noqa: E402

load_dotenv(ROOT / ".env", override=True)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
SCHEMA = "lab_swarm"
HARDER = ROOT / "data" / "evals" / "harder"


def load(name):
    """Read one of the JSON files of the harder claims."""
    return json.loads((HARDER / name).read_text(encoding="utf-8"))


claims = {claim["claim_id"]: claim for claim in load("claims.json")}
labels = {decision["claim_id"]: decision for decision in load("decisions.json")}
policies = {policy["policy_id"]: policy for policy in load("policies.json")}
policy_wording = (ROOT / "data" / "policy_wording.md").read_text(encoding="utf-8")

INSTRUCTIONS = """You are a claims handler at UnderCover Travel Insurance.
Decide the claim you are given, using the policy wording below and the customer's policy record.

Choose one decision:
- approve: the wording covers the claim and the required documents are attached. Work out the payout using section 10.
- decline: the wording does not cover the claim.
- refer: a colleague needs to look at it, because a required document is missing, or the story and the documents disagree, or the wording does not settle the question.

Use your tools to record your decision.
Use the payout tool to work out the payout on an approved claim, and record the payout it returns.
"""


def make_user_prompt(claim):
    """The customer's policy record and the claim, as JSON."""
    policy = policies[claim["policy_id"]]
    return f"""# Policy record

{json.dumps(policy, indent=2)}

# Claim

{json.dumps(claim, indent=2)}
"""


# The decisions recorded in this process. They live in memory, so a crash loses them.
recorded = {}


@tool(parse_docstring=True)
def record_decision(
    claim_id: str,
    rationale: str,
    decision: Literal["approve", "decline", "refer"],
    payout: float,
) -> str:
    """Record the decision on a claim in the claims system.

    Args:
        claim_id: The claim's id
        rationale: 2-3 sentences to explain the decision along with the relevant section of the policy
        decision: The decision on the claim
        payout: The amount to pay in US dollars, or 0 for a decline or a referral
    """
    if claim_id in recorded:
        return f"A decision is already recorded on {claim_id}, and decisions are final"
    if decision == "approve" and payout <= 0:
        return "An approval needs a payout above zero"
    recorded[claim_id] = {
        "decision": decision,
        "payout": payout,
        "rationale": rationale,
    }
    return f"Recorded {decision} on {claim_id}"


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


luna = ChatOpenAI(
    model="openai/gpt-6-luna",
    base_url=OPENROUTER_BASE_URL,
    api_key=os.getenv("OPENROUTER_API_KEY"),
    reasoning_effort="low",
    timeout=120,
    max_retries=5,
)
payout_agent = create_agent(
    model=luna,
    tools=[record_decision, calculate_payout],
    system_prompt=f"{INSTRUCTIONS}\n{policy_wording}\n",
)


def work_claim(claim_id):
    """Run the claim agent on one claim and return its result."""
    started = datetime.now()
    print(f"Working {claim_id}", flush=True)
    result = payout_agent.invoke(
        {"messages": [{"role": "user", "content": make_user_prompt(claims[claim_id])}]}
    )
    answer = recorded.get(
        claim_id, {"decision": "refer", "payout": 0.0, "rationale": "Nothing recorded"}
    )
    cost = sum(
        message.response_metadata["token_usage"]["cost"]
        for message in result["messages"]
        if message.type == "ai"
    )
    print(
        f"Finished {claim_id}: {answer['decision']} ${answer['payout']:,.2f}, cost ${cost:.5f}",
        flush=True,
    )
    return {
        "results": [
            {
                "claim_id": claim_id,
                **answer,
                "cost": cost,
                "started": started,
                "finished": datetime.now(),
            }
        ]
    }


WRONGFUL_DECLINE = 1500
NEEDLESS_REFERRAL = 50


def is_right(answer, expected):
    """True when the decision matches the handler's and the payout is within a dollar."""
    return (
        answer["decision"] == expected["decision"]
        and abs(answer["payout"] - expected["payout"]) <= 1
    )


def mistake_cost(answer, expected):
    """What the agent's answer costs UnderCover, against the handler's decision."""
    if answer["decision"] == expected["decision"]:
        return (
            abs(answer["payout"] - expected["payout"])
            if answer["decision"] == "approve"
            else 0
        )
    if answer["decision"] == "decline":
        return WRONGFUL_DECLINE
    if answer["decision"] == "approve":
        return answer["payout"]
    return NEEDLESS_REFERRAL


def score_table(results):
    """One row for each claim in a run: the agent's answer beside the handler's, with the scores."""
    rows = []
    for answer in results:
        expected = labels[answer["claim_id"]]
        rows.append(
            {
                "claim_id": answer["claim_id"],
                "handler": expected["decision"],
                "agent": answer["decision"],
                "handler_payout": expected["payout"],
                "agent_payout": answer["payout"],
                "right": is_right(answer, expected),
                "mistake_cost": mistake_cost(answer, expected),
                "llm_cost": answer["cost"],
                "started": answer["started"],
                "finished": answer["finished"],
                "seconds": (answer["finished"] - answer["started"]).total_seconds(),
                "rationale": answer["rationale"],
            }
        )
    return pd.DataFrame(rows).sort_values("claim_id")


def run_scores(table):
    """The scores for a whole run: quality, cost and time."""
    return {
        "claims": len(table),
        "decision_accuracy": (table["agent"] == table["handler"]).mean(),
        "accuracy": table["right"].mean(),
        "cost_of_mistakes": table["mistake_cost"].sum(),
        "straight_through": (table["agent"] != "refer").mean(),
        "llm_cost": table["llm_cost"].sum(),
        "seconds": (table["finished"].max() - table["started"].min()).total_seconds(),
        "slowest_claim": table["seconds"].max(),
        "seconds_per_claim": table["seconds"].mean(),
    }


class Dispatch(TypedDict):
    """What the dispatcher keeps for one run."""

    claims: list[str]
    results: Annotated[list, operator.add]
    scores: dict


def list_claims(state: Dispatch):
    """The claims to work in this run: the ones given, or every claim."""
    return {"claims": state.get("claims") or list(claims)}


def fan_out(state: Dispatch):
    """Send each claim to a claim agent."""
    return [Send("work_claim", claim_id) for claim_id in state["claims"]]


# How many times score_run has run in this process, to show it runs once per run
score_runs = []


def score_run(state: Dispatch):
    """Score the whole run, once every claim agent has finished."""
    score_runs.append(len(state["results"]))
    scores = run_scores(score_table(state["results"]))
    return {"scores": {name: float(value) for name, value in scores.items()}}


def gated(work, at_once):
    """The work function, with no more than at_once claims running at the same time."""
    gate = threading.BoundedSemaphore(at_once)

    def work_when_free(claim_id):
        with gate:
            return work(claim_id)

    return work_when_free


def build_dispatcher(work=work_claim, checkpointer=None, at_once=None):
    """The dispatcher: list the claims, fan out to a claim agent each, then score the run.

    With at_once, the claims wait at a gate inside the node, so run it with run_config(at_once=...),
    which leaves LangGraph threads free to save each claim's result as it finishes.
    """
    builder = StateGraph(Dispatch)
    builder.add_node("list_claims", list_claims)
    builder.add_node(
        "work_claim",
        gated(work, at_once) if at_once else work,
        retry_policy=RetryPolicy(max_attempts=3),
    )
    builder.add_node("score_run", score_run)
    builder.add_edge(START, "list_claims")
    builder.add_conditional_edges("list_claims", fan_out, ["work_claim"])
    builder.add_edge("work_claim", "score_run")
    builder.add_edge("score_run", END)
    return builder.compile(checkpointer=checkpointer)


def connect():
    """A connection to Supabase for the checkpointer, in a schema of its own."""
    connection = psycopg.connect(
        os.getenv("DATABASE_URL"),
        autocommit=True,
        prepare_threshold=0,
        row_factory=dict_row,
        options=f"-c search_path={SCHEMA}",
    )
    connection.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
    return connection


def postgres_checkpointer(connection):
    """Day 3's PostgresSaver, with its tables set up."""
    checkpointer = PostgresSaver(connection)
    checkpointer.setup()
    return checkpointer


def run_config(thread_id, max_concurrency=None, at_once=None):
    """The config for a run on a thread.

    max_concurrency caps the claims at once as the lab does. LangGraph runs the nodes and saves their
    results on one pool of max_concurrency threads, so a result waits to be saved behind the claims
    still queued. With at_once, the gate in the node caps the claims, and the pool has a thread for
    every claim and a few to spare, so each result is saved as soon as its claim finishes.
    """
    pool = len(claims) + 5 if at_once else max_concurrency
    return {"configurable": {"thread_id": thread_id}, "max_concurrency": pool}


def main():
    parser = argparse.ArgumentParser(
        description="Run the swarm on a thread saved in Supabase"
    )
    parser.add_argument("thread_id")
    parser.add_argument(
        "--durability", choices=["sync", "async", "exit"], default="sync"
    )
    cap = parser.add_mutually_exclusive_group()
    cap.add_argument(
        "--max-concurrency",
        type=int,
        default=5,
        help="Cap the claims at once as the lab does",
    )
    cap.add_argument(
        "--at-once", type=int, help="Cap the claims at once with a gate in the node"
    )
    args = parser.parse_args()

    connection = connect()
    dispatcher = build_dispatcher(
        checkpointer=postgres_checkpointer(connection), at_once=args.at_once
    )
    config = run_config(args.thread_id, args.max_concurrency, args.at_once)
    result = dispatcher.invoke({}, config, durability=args.durability)
    print(f"Scores: {result['scores']}", flush=True)


if __name__ == "__main__":
    main()
