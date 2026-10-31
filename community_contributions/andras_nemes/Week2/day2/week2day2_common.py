"""Shared setup for the Week 2 Day 2 assignment: the lab's agent, tools, scoring and experiment loop, with the customer notes."""

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date
from functools import partial
from pathlib import Path
from time import perf_counter
from typing import Literal

import httpx
import pandas as pd
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langfuse import Evaluation, get_client
from langfuse.langchain import CallbackHandler

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "labs"))
from week2day1_payout import Benefit, Line, Payout, work_out_payout  # noqa: E402

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
RESULTS.mkdir(exist_ok=True)

load_dotenv(REPO / ".env", override=True)
langfuse = get_client()
DATA = REPO / "data"
EVEN_HARDER = DATA / "evals" / "even_harder"
claims = json.loads((EVEN_HARDER / "claims.json").read_text(encoding="utf-8"))
labels = {decision["claim_id"]: decision for decision in json.loads((EVEN_HARDER / "decisions.json").read_text(encoding="utf-8"))}
policies = {policy["policy_id"]: policy for policy in json.loads((EVEN_HARDER / "policies.json").read_text(encoding="utf-8"))}
policy_wording = (DATA / "policy_wording.md").read_text(encoding="utf-8")
knowledge = json.loads((DATA / "knowledge.json").read_text(encoding="utf-8"))

# The memory the lab taught in Part 3, from a read-only Qdrant server

if sys.platform == "win32":
    import langchain_mcp_adapters.sessions as mcp_sessions

    mcp_sessions.stdio_client = partial(mcp_sessions.stdio_client, errlog=subprocess.DEVNULL)

MEMORY_ENV = {"QDRANT_LOCAL_PATH": str(REPO / "labs" / "qdrant_data"), "COLLECTION_NAME": "memory", "QDRANT_READ_ONLY": "true"}


async def memory_search_tools():
    """qdrant-find from a read-only Qdrant server, as in the lab's Part 4."""
    client = MultiServerMCPClient({"memory": {"transport": "stdio", "command": "uvx", "args": ["--python", "3.12.12", "mcp-server-qdrant@0.8.1"], "env": MEMORY_ENV}})
    return [memory_tool for memory_tool in await client.get_tools() if memory_tool.name == "qdrant-find"]


# The UnderCover agent, as in the lab

http_client = httpx.AsyncClient(limits=httpx.Limits(max_keepalive_connections=0))
luna = ChatOpenAI(model="openai/gpt-6-luna", base_url="https://openrouter.ai/api/v1", api_key=os.getenv("OPENROUTER_API_KEY"), reasoning_effort="low", timeout=120, max_retries=5, http_async_client=http_client)

INSTRUCTIONS = """You are a claims handler at UnderCover Travel Insurance.
Decide the claim you are given, using the policy wording below and the customer's policy record.

Choose one decision:
- approve: the wording covers the claim and the required documents are attached. Work out the payout using section 10.
- decline: the wording does not cover the claim.
- refer: a colleague needs to look at it, because a required document is missing, or the story and the documents disagree, or the wording does not settle the question.

Use your tools to record your decision.
"""
PAYOUT_TOOL_LINE = "Use the payout tool to work out the payout on an approved claim, and record the payout it returns.\n"
MEMORY_LINE = "Before you decide, search your memory for any product, event or place in the claim that you need to know more about.\n"


def make_system_prompt(*extra_lines):
    """The lab's system prompt, with a line for each of the agent's other tools."""
    return f"{INSTRUCTIONS}{PAYOUT_TOOL_LINE}{''.join(extra_lines)}\n{policy_wording}\n"


def make_user_prompt(claim):
    """The customer's policy record and the claim, as JSON."""
    return f"# Policy record\n\n{json.dumps(policies[claim['policy_id']], indent=2)}\n\n# Claim\n\n{json.dumps(claim, indent=2)}\n"


recorded = {}


@tool(parse_docstring=True)
def record_decision(claim_id: str, rationale: str, decision: Literal["approve", "decline", "refer"], payout: float) -> str:
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
    recorded[claim_id] = {"decision": decision, "payout": payout, "rationale": rationale}
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


# Task 2: the customer notes, a Markdown file for each customer_id

SEED_NOTES = {
    'CUS-3301': '# Customer notes: CUS-3301, Gloria Benitez\n\n- 2024-02-06 (Dana Whitfield): Called to update her mailing address after moving within Miami. Prefers to be contacted by email.\n- 2025-05-14 (Marcus Oyelaran): Asked whether her policy covers her husband Ramon when they travel together. Explained that each traveller is named on the policy record.\n',
    'CUS-3307': '# Customer notes: CUS-3307, Brandon Lee\n\n- 2026-06-03 (Marcus Oyelaran): Called before buying a Premium policy with Electronics Plus for a trip to Japan. Asked which devices Electronics Plus covers; emailed him the list from the policy wording.\n',
    'CUS-3314': '# Customer notes: CUS-3314, Ryan Mitchell\n\n- 2026-06-12 (Dana Whitfield): Asked whether scuba diving is covered on a trip to Honduras. Told him the policy wording sets out which dives count as adventure sports, and that those need the Adventure Sports add-on.\n',
    'CUS-3320': '# Customer notes: CUS-3320, Ruth Abernathy\n\n- 2022-09-30 (Dana Whitfield): Long-standing customer. Hard of hearing, so she asks for anything important to be confirmed in writing as well as by phone.\n',
    'CUS-3322': '# Customer notes: CUS-3322, Alice Thornton\n\n- 2025-11-18 (Marcus Oyelaran): Travels often to Scotland for work. Prefers email and replies quickly.\n',
    'CUS-3324': '# Customer notes: CUS-3324, Laura Bennett\n\n- 2026-07-20 (Marcus Oyelaran): Called from Amsterdam to say her bag was snatched from her bicycle basket the evening before. Told her a theft claim needs a copy of the police report. She has made a report and the police will email it to her; she will send it on when it comes.\n',
    'CUS-3325': "# Customer notes: CUS-3325, George Papadakis\n\n- 2026-08-05 (Dana Whitfield): Called from Santorini after a fall at his hotel. Reminded him that a medical claim needs the clinic's itemized bill, not only a receipt for the total. The clinic told him the itemized bill would follow by email.\n",
}
NOTES = HERE / "customer_notes"


def reset_notes(run=None):
    """Start the notes again from the starting notes, before each run."""
    shutil.rmtree(NOTES, ignore_errors=True)
    NOTES.mkdir()
    for customer_id, notes in SEED_NOTES.items():
        (NOTES / f"{customer_id}.md").write_text(notes, encoding="utf-8")


def keep_notes(slug):
    """An after_run step that saves the notes as a run left them."""
    return lambda run: shutil.copytree(NOTES, RESULTS / f"notes_{slug}_run_{run}", dirs_exist_ok=True)


def notes_file(customer_id):
    """The notes file for a customer, or None for anything that isn't a customer id."""
    return NOTES / f"{customer_id}.md" if re.fullmatch(r"CUS-\d{4}", customer_id) else None


@tool(parse_docstring=True)
def read_customer_notes(customer_id: str) -> str:
    """Read UnderCover's notes on a customer: earlier calls, claims and anything still outstanding.

    Args:
        customer_id: The customer's id, such as CUS-1234
    """
    path = notes_file(customer_id)
    if path is None:
        return f"{customer_id} is not a customer id like CUS-1234"
    return path.read_text(encoding="utf-8") if path.exists() else f"There are no notes on {customer_id} yet"


@tool(parse_docstring=True)
def add_customer_note(customer_id: str, note: str) -> str:
    """Add a note to a customer's notes, for the next handler who deals with them.

    Args:
        customer_id: The customer's id, such as CUS-1234
        note: 1-2 sentences for the next handler
    """
    path = notes_file(customer_id)
    if path is None:
        return f"{customer_id} is not a customer id like CUS-1234"
    if not path.exists():
        path.write_text(f"# Customer notes: {customer_id}\n\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as notes:
        notes.write(f"- {date.today().isoformat()} (UnderCover Agent): {note.strip()}\n")
    return f"Added a note to {customer_id}"


# The task

langfuse_handler = CallbackHandler()


async def decide(agent, claim, search_tools):
    """Run an agent on one claim and return its decision, cost, time and what its searches returned.

    Changed from the lab: the search tools are a parameter, and a sub-agent tool's artifact adds its searches and cost.
    `retrieved` is what the searches found; `relayed` is what of it reached the agent that decides.
    """
    start = perf_counter()
    result = await agent.ainvoke({"messages": [{"role": "user", "content": make_user_prompt(claim)}]}, config={"callbacks": [langfuse_handler]})
    answer = recorded.get(claim["claim_id"], {"decision": "refer", "payout": 0.0, "rationale": "Nothing recorded"})
    cost = sum(message.response_metadata["token_usage"]["cost"] for message in result["messages"] if message.type == "ai")
    tool_messages = [message for message in result["messages"] if message.type == "tool"]
    retrieved = [message.text for message in tool_messages if message.name in search_tools]
    relayed = list(retrieved)
    sub_agent_cost = 0.0
    for message in tool_messages:
        if isinstance(message.artifact, dict) and "retrieved" in message.artifact:
            sub_agent_cost += message.artifact["cost"]
            retrieved.append(message.artifact["retrieved"])
            relayed.append(message.text)
    print(f"{claim['claim_id']}: {answer['decision']} ${answer['payout']:,.2f}")
    return {**answer, "cost": cost + sub_agent_cost, "sub_agent_cost": sub_agent_cost, "seconds": perf_counter() - start,
            "retrieved": "\n".join(retrieved), "relayed": "\n".join(relayed), "tool_calls": [message.name for message in tool_messages]}


# Scoring, as in the lab, with relayed_fact and the time added

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
    return answer["payout"] if answer["decision"] == "approve" else NEEDLESS_REFERRAL


def has_fact(answer, expected, field):
    """For a claim that needs a fact, whether it is in the answer's retrieved or relayed text."""
    return all(fact in answer[field] for fact in expected["needs"]) if expected["needs"] else None


def kappa(table):
    """Cohen's kappa for the agent's decisions against the handlers'."""
    observed = (table["agent"] == table["handler"]).mean()
    agent_share, handler_share = table["agent"].value_counts(normalize=True), table["handler"].value_counts(normalize=True)
    expected = sum(agent_share.get(decision, 0) * handler_share.get(decision, 0) for decision in ["approve", "decline", "refer"])
    return (observed - expected) / (1 - expected) if expected != 1 else float("nan")


def score_claim(*, output, expected_output, **kwargs):
    """Item evaluator: right, the cost of the mistake, and whether the fact was found and relayed."""
    evaluations = [Evaluation(name="right", value=int(is_right(output, expected_output))),
                   Evaluation(name="mistake_cost", value=mistake_cost(output, expected_output))]
    if expected_output["needs"]:
        for field, name in [("retrieved", "found_fact"), ("relayed", "relayed_fact")]:
            evaluations.append(Evaluation(name=name, value=int(has_fact(output, expected_output, field))))
    return evaluations


def score_table(item_results):
    """One row for each claim in a run: the agent's answer beside the handler's, with the scores."""
    rows = []
    for result in item_results:
        answer, expected = result.output, result.item.expected_output
        if answer is None:
            continue
        rows.append({
            "claim_id": result.item.id, "handler": expected["decision"], "agent": answer["decision"],
            "handler_payout": expected["payout"], "agent_payout": answer["payout"],
            "right": is_right(answer, expected), "mistake_cost": mistake_cost(answer, expected),
            "found_fact": has_fact(answer, expected, "retrieved"), "relayed_fact": has_fact(answer, expected, "relayed"),
            "llm_cost": answer["cost"], "sub_agent_cost": answer["sub_agent_cost"], "seconds": answer["seconds"],
            "tool_calls": answer["tool_calls"], "relayed": answer["relayed"], "rationale": answer["rationale"],
        })
    return pd.DataFrame(rows).sort_values("claim_id")


def run_scores(table):
    """The scores for a whole run."""
    return {
        "accuracy": table["right"].mean(),
        "kappa": kappa(table),
        "cost_of_mistakes": table["mistake_cost"].sum(),
        "straight_through": (table["agent"] != "refer").mean(),
        "found_fact": table["found_fact"].dropna().astype(float).mean(),
        "relayed_fact": table["relayed_fact"].dropna().astype(float).mean(),
        "llm_cost": table["llm_cost"].sum(),
        "seconds_per_claim": table["seconds"].mean(),
    }


def score_run(*, item_results, **kwargs):
    """Run evaluator: the scores for the whole run."""
    return [Evaluation(name=name, value=float(value)) for name, value in run_scores(score_table(item_results)).items()]


# The experiments: N_TIMES runs each, saved so that no run is paid for twice

N_TIMES = 3


def load_runs(slug, runs=N_TIMES):
    """The saved tables of an experiment's runs, as one table."""
    return pd.concat([pd.DataFrame(json.loads((RESULTS / f"{slug}_run_{run}.json").read_text(encoding="utf-8"))) for run in range(1, runs + 1)], ignore_index=True)


def run_experiment(name, task, slug, runs=N_TIMES, before_run=None, after_run=None):
    """Run an experiment on the lab's dataset, as in the lab, loading any run already saved in results/."""
    items = langfuse.get_dataset("even-harder-claims").items
    for run in range(1, runs + 1):
        path = RESULTS / f"{slug}_run_{run}.json"
        if path.exists():
            continue
        recorded.clear()
        if before_run:
            before_run(run)
        result = langfuse.run_experiment(name=name, data=items, task=task, evaluators=[score_claim], run_evaluators=[score_run], max_concurrency=1)
        table = score_table(result.item_results).assign(run=run)
        if len(table) != len(items):
            raise RuntimeError(f"{name}, run {run}: only {len(table)} of {len(items)} claims finished")
        if after_run:
            after_run(run)
        path.write_text(table.to_json(orient="records", indent=2), encoding="utf-8")
    langfuse.flush()
    return load_runs(slug, runs)


def compare(tables):
    """The scores of several experiments averaged over their runs, one row each."""
    return pd.DataFrame([pd.DataFrame([run_scores(run) for _, run in table.groupby("run")]).mean() for table in tables.values()], index=list(tables)).round(3)


def by_claim(tables, column="right"):
    """For each claim, how many runs of each experiment have the column true, blank where it doesn't apply."""
    def count(values):
        return values.dropna().astype(int).sum() if values.notna().any() else None
    return pd.concat([table.groupby("claim_id")[column].apply(count).rename(name) for name, table in tables.items()], axis=1)
