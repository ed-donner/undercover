"""The dispatcher for the Week 2 Day 4 challenge, shared by the notebook and the stretch.

The notebook imports it. For the stretch the notebook runs `main` as a process of its own and
kills it partway through a dispatch, as a kernel restart would. `main` also runs from the
command line:

    uv run python week2day4_swarm.py <thread id> <stand-in|agent> <cap|gate> <agents at once> <sync|exit>

`cap` limits the agents with `max_concurrency`, as the lab does. `gate` lets every claim start and
holds all but N of them at a semaphore, so LangGraph's thread pool always has a thread free to save
a finished claim.
"""

import functools
import json
import operator
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal, TypedDict

import pandas as pd
import psycopg
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.callbacks import BaseCallbackHandler
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
HARDER = ROOT / "data" / "evals" / "harder"


def load(name):
    """Read one of the JSON files of the harder claims."""
    return json.loads((HARDER / name).read_text(encoding="utf-8"))


claims = {claim["claim_id"]: claim for claim in load("claims.json")}
labels = {decision["claim_id"]: decision for decision in load("decisions.json")}
policies = {policy["policy_id"]: policy for policy in load("policies.json")}
policy_wording = (ROOT / "data" / "policy_wording.md").read_text(encoding="utf-8")


# The lab's dispatcher, with a score_run node and the scores in the state


class Dispatch(TypedDict):
    """What the dispatcher keeps for one run."""

    claims: list[str]
    results: Annotated[list, operator.add]
    scores: dict


def list_claims(state: Dispatch):
    """The claims to work in this run."""
    return {"claims": list(claims)}


def fan_out(state: Dispatch):
    """Send each claim to a claim agent."""
    return [Send("work_claim", claim_id) for claim_id in state["claims"]]


WRONGFUL_DECLINE = 1500
NEEDLESS_REFERRAL = 50


def is_right(answer, expected):
    """True when the decision matches the handler's and the payout is within a dollar."""
    return answer["decision"] == expected["decision"] and abs(answer["payout"] - expected["payout"]) <= 1


def mistake_cost(answer, expected):
    """What the agent's answer costs UnderCover, against the handler's decision."""
    if answer["decision"] == expected["decision"]:
        return abs(answer["payout"] - expected["payout"]) if answer["decision"] == "approve" else 0
    if answer["decision"] == "decline":
        return WRONGFUL_DECLINE
    if answer["decision"] == "approve":
        return answer["payout"]
    return NEEDLESS_REFERRAL


def time_scores(results):
    """How long a run took: from the first claim starting to the last finishing, and per claim."""
    table = pd.DataFrame(results)
    took = (table["finished"] - table["started"]).dt.total_seconds()
    return {
        "claims": len(table),
        "seconds": (table["finished"].max() - table["started"].min()).total_seconds(),
        "slowest_claim": float(took.max()),
        "seconds_per_claim": float(took.mean()),
    }


def quality_scores(results):
    """The lab's measures of quality and cost, against the handlers' decisions."""
    rows = [(answer, labels[answer["claim_id"]]) for answer in results]
    return {
        "decision_accuracy": sum(a["decision"] == e["decision"] for a, e in rows) / len(rows),
        "accuracy": sum(is_right(a, e) for a, e in rows) / len(rows),
        "cost_of_mistakes": sum(mistake_cost(a, e) for a, e in rows),
        "straight_through": sum(a["decision"] != "refer" for a, _ in rows) / len(rows),
        "llm_cost": sum(a["cost"] for a, _ in rows),
    }


score_runs = []


def score_run(state: Dispatch):
    """Score the whole run, once every claim agent has finished. A stand-in's results have no
    decisions, so they get only the times."""
    results = state["results"]
    score_runs.append(len(results))
    scores = time_scores(results)
    if all("decision" in result for result in results):
        scores = quality_scores(results) | scores
    return {"scores": scores}


def build_dispatcher(worker, checkpointer=None):
    """The lab's dispatcher, with score_run after the claim agents."""
    builder = StateGraph(Dispatch)
    builder.add_node("list_claims", list_claims)
    builder.add_node("work_claim", worker, retry_policy=RetryPolicy(max_attempts=3))
    builder.add_node("score_run", score_run)
    builder.add_edge(START, "list_claims")
    builder.add_conditional_edges("list_claims", fan_out, ["work_claim"])
    builder.add_edge("work_claim", "score_run")
    builder.add_edge("score_run", END)
    return builder.compile(checkpointer=checkpointer)


# Where the claim agents record their decisions and each start of work on a claim


class MemoryRecords:
    """The lab's way: decisions in a dict, which a restart forgets."""

    def __init__(self):
        self.decisions = {}

    def started(self, claim_id):
        pass

    def finished(self, claim_id):
        pass

    def record(self, claim_id, decision, payout, rationale):
        """Record a decision once; False when one is already recorded."""
        if claim_id in self.decisions:
            return False
        self.decisions[claim_id] = {"decision": decision, "payout": payout, "rationale": rationale}
        return True

    def decision(self, claim_id):
        return self.decisions.get(claim_id)


class TableRecords:
    """Decisions and attempts in Supabase, for one dispatch thread, so they outlive a restart."""

    def __init__(self, connection, thread_id):
        self.connection = connection
        self.thread_id = thread_id

    def started(self, claim_id):
        self.connection.execute(
            "INSERT INTO swarm_attempts (thread_id, claim_id, pid) VALUES (%s, %s, %s)",
            (self.thread_id, claim_id, os.getpid()),
        )

    def finished(self, claim_id):
        """Mark this process's latest attempt on the claim finished, so an attempt that failed before a retry stays unfinished."""
        self.connection.execute(
            """UPDATE swarm_attempts SET finished_at = now() WHERE ctid = (
                SELECT ctid FROM swarm_attempts WHERE thread_id = %s AND claim_id = %s AND pid = %s AND finished_at IS NULL
                ORDER BY started_at DESC LIMIT 1)""",
            (self.thread_id, claim_id, os.getpid()),
        )

    def record(self, claim_id, decision, payout, rationale):
        """Record a decision once; False, and the refusal noted, when one is already recorded."""
        row = self.connection.execute(
            """INSERT INTO swarm_decisions (thread_id, claim_id, decision, payout, rationale, pid)
            VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING RETURNING claim_id""",
            (self.thread_id, claim_id, decision, payout, rationale, os.getpid()),
        ).fetchone()
        if row is None:
            self.connection.execute(
                "INSERT INTO swarm_refusals (thread_id, claim_id, pid) VALUES (%s, %s, %s)",
                (self.thread_id, claim_id, os.getpid()),
            )
        return row is not None

    def decision(self, claim_id):
        query = "SELECT decision, payout, rationale FROM swarm_decisions WHERE thread_id = %s AND claim_id = %s"
        row = self.connection.execute(query, (self.thread_id, claim_id)).fetchone()
        return row and {**row, "payout": float(row["payout"])}


class Records:
    """Where the claim agents record: in memory, unless a dispatch is given its table."""

    def __init__(self):
        self.store = MemoryRecords()

    def use(self, store):
        self.store = store


records = Records()


def connect():
    """A connection to Supabase in the lab's schema, with the stretch's two tables."""
    connection = psycopg.connect(
        os.environ["DATABASE_URL"], autocommit=True, prepare_threshold=0, row_factory=dict_row, options="-c search_path=lab"
    )
    connection.execute("CREATE SCHEMA IF NOT EXISTS lab")
    connection.execute("""CREATE TABLE IF NOT EXISTS swarm_decisions (
        thread_id TEXT, claim_id TEXT, decision TEXT NOT NULL, payout NUMERIC NOT NULL, rationale TEXT,
        recorded_at TIMESTAMPTZ DEFAULT now(), PRIMARY KEY (thread_id, claim_id))""")
    connection.execute("""CREATE TABLE IF NOT EXISTS swarm_attempts (
        thread_id TEXT, claim_id TEXT, pid INTEGER, started_at TIMESTAMPTZ DEFAULT now(), finished_at TIMESTAMPTZ)""")
    connection.execute("ALTER TABLE swarm_decisions ADD COLUMN IF NOT EXISTS pid INTEGER")
    connection.execute("""CREATE TABLE IF NOT EXISTS swarm_refusals (
        thread_id TEXT, claim_id TEXT, pid INTEGER, refused_at TIMESTAMPTZ DEFAULT now())""")
    return connection


# The workers: the lab's stand-in, and its claim agent with the payout tool

STAND_IN_SECONDS = 1


def stand_in(claim_id):
    """Pretend to work a claim for one, two or three seconds, so the claims finish at different times."""
    records.store.started(claim_id)
    started = datetime.now()
    time.sleep(STAND_IN_SECONDS * (1 + int(claim_id[-1]) % 3))
    records.store.finished(claim_id)
    return {"results": [{"claim_id": claim_id, "started": started, "finished": datetime.now()}]}


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


@tool(parse_docstring=True)
def record_decision(claim_id: str, rationale: str, decision: Literal["approve", "decline", "refer"], payout: float) -> str:
    """Record the decision on a claim in the claims system.

    Args:
        claim_id: The claim's id
        rationale: 2-3 sentences to explain the decision along with the relevant section of the policy
        decision: The decision on the claim
        payout: The amount to pay in US dollars, or 0 for a decline or a referral
    """
    if decision == "approve" and payout <= 0:
        return "An approval needs a payout above zero"
    if not records.store.record(claim_id, decision, payout, rationale):
        return f"A decision is already recorded on {claim_id}, and decisions are final"
    return f"Recorded {decision} on {claim_id}"


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


@functools.cache
def payout_agent():
    """The lab's claim agent, built on first use, so the stand-in needs no OpenRouter key."""
    luna = ChatOpenAI(
        model="openai/gpt-6-luna",
        base_url=OPENROUTER_BASE_URL,
        api_key=os.getenv("OPENROUTER_API_KEY"),
        reasoning_effort="low",
        timeout=120,
        max_retries=5,
    )
    return create_agent(model=luna, tools=[record_decision, calculate_payout], system_prompt=f"{INSTRUCTIONS}\n{policy_wording}\n")


def work_claim(claim_id):
    """Run the claim agent on one claim and return its result."""
    records.store.started(claim_id)
    started = datetime.now()
    result = payout_agent().invoke({"messages": [{"role": "user", "content": make_user_prompt(claims[claim_id])}]})
    answer = records.store.decision(claim_id) or {"decision": "refer", "payout": 0.0, "rationale": "Nothing recorded"}
    cost = sum(message.response_metadata["token_usage"]["cost"] for message in result["messages"] if message.type == "ai")
    records.store.finished(claim_id)
    return {"results": [{"claim_id": claim_id, **answer, "cost": cost, "started": started, "finished": datetime.now()}]}


WORKERS = {"stand-in": stand_in, "agent": work_claim}


class ModelCalls(BaseCallbackHandler):
    """Counts the model calls made in this process, and what they cost."""

    def __init__(self):
        self.lock = threading.Lock()
        self.calls = 0
        self.cost = 0.0

    def on_llm_end(self, response, **kwargs):
        usage = response.generations[0][0].message.response_metadata.get("token_usage", {})
        with self.lock:
            self.calls += 1
            self.cost += usage.get("cost", 0.0)


def gated(worker, agents):
    """The worker, with at most `agents` of it working at once."""
    gate = threading.Semaphore(agents)

    def through_gate(claim_id):
        with gate:
            return worker(claim_id)

    return through_gate


def dispatch_setup(worker, limit, agents):
    """The worker and the config's max_concurrency for a cap or a gate of `agents`."""
    if limit == "cap":
        return WORKERS[worker], agents
    return gated(WORKERS[worker], agents), len(claims) + 1


def main(thread_id, worker, limit, agents, durability):
    """Run one dispatch on its own thread in Supabase, until it finishes or is killed."""
    with connect() as connection, connect() as saved:
        records.use(TableRecords(connection, thread_id))
        checkpointer = PostgresSaver(saved)
        checkpointer.setup()
        node, concurrency = dispatch_setup(worker, limit, agents)
        dispatcher = build_dispatcher(node, checkpointer)
        config = {"configurable": {"thread_id": thread_id}, "max_concurrency": concurrency}
        result = dispatcher.invoke({}, config, durability=durability)
        print(json.dumps(result["scores"], default=str))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5])
