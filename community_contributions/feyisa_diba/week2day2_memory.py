"""Feyisa Diba's Week 2 Day 2 assignment: the UnderCover agent with a memory, five ways.

The notebook week2day2_memory.ipynb explains the experiments and analyses them. This module holds the agents,
their tools and the runs, so that the runs can also go from the command line, each saved to
week2day2_memory_results.csv:

    uv run python week2day2_memory.py "Payout tool:1" "Qdrant:1" "Word lookup:1"

OpenRouter limits new accounts to 20 requests a minute for GPT-6 Luna, so run one process at a time.
"""

import argparse
import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import date
from functools import partial
from pathlib import Path
from typing import Literal

import httpx
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.middleware import ToolRetryMiddleware
from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_openai import ChatOpenAI
from langfuse import Evaluation, get_client
from langfuse.langchain import CallbackHandler

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(REPO_ROOT / "labs"))
from week2day1_payout import Benefit, Line, Payout, work_out_payout  # noqa: E402

# The lab's adjustment for Windows: the library that launches MCP servers needs a real file for their error log
if sys.platform == "win32":
    import langchain_mcp_adapters.sessions as mcp_sessions

    mcp_sessions.stdio_client = partial(mcp_sessions.stdio_client, errlog=subprocess.DEVNULL)

load_dotenv(REPO_ROOT / ".env", override=True)
langfuse = get_client()
langfuse_handler = CallbackHandler()

# The data

EVEN_HARDER = REPO_ROOT / "data" / "evals" / "even_harder"


def load(name):
    """Read one of the JSON files of the even harder claims."""
    return json.loads((EVEN_HARDER / name).read_text(encoding="utf-8"))


claims = load("claims.json")
labels = {decision["claim_id"]: decision for decision in load("decisions.json")}
policies = {policy["policy_id"]: policy for policy in load("policies.json")}
policy_wording = (REPO_ROOT / "data" / "policy_wording.md").read_text(encoding="utf-8")
knowledge = json.loads((REPO_ROOT / "data" / "knowledge.json").read_text(encoding="utf-8"))
CUSTOMER_IDS = {claim["customer_id"] for claim in claims}

# The model and the lab's prompts


class TimedRateLimiter(InMemoryRateLimiter):
    """LangChain's rate limiter, keeping count of the time spent waiting, so that it can be left out of the time a claim takes."""

    waited = 0.0

    async def aacquire(self, *, blocking=True):
        start = time.perf_counter()
        acquired = await super().aacquire(blocking=blocking)
        self.waited += time.perf_counter() - start
        return acquired


# OpenRouter allows new accounts 20 requests a minute for GPT-6 Luna. Every model call, the sub-agent's too,
# waits its turn here: 17 a minute, with bursts of 2, so no minute has more than 19.
rate_limiter = TimedRateLimiter(requests_per_second=17 / 60, max_bucket_size=2)

http_client = httpx.AsyncClient(limits=httpx.Limits(max_keepalive_connections=0))
luna = ChatOpenAI(
    model="openai/gpt-6-luna",
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    reasoning_effort="low",
    timeout=120,
    max_retries=5,
    http_async_client=http_client,
    rate_limiter=rate_limiter,
)

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
NOTES_LINE = "Before you decide, read the customer's notes. Once you have recorded your decision, add a short note to the customer's notes for the next handler.\n"
RESEARCH_LINE = "Before you decide, ask your research assistant about any product, event or place in the claim that you need to know more about, and for the customer's notes. Once you have recorded your decision, ask it to add a short note to the customer's notes for the next handler.\n"


def system_prompt(*lines):
    """The lab's instructions, the payout tool line, any further lines, and the policy wording."""
    return f"{INSTRUCTIONS}{PAYOUT_TOOL_LINE}{''.join(lines)}\n{policy_wording}\n"


def make_user_prompt(claim):
    """The customer's policy record and the claim, as JSON."""
    policy = policies[claim["policy_id"]]
    return f"""# Policy record

{json.dumps(policy, indent=2)}

# Claim

{json.dumps(claim, indent=2)}
"""


# What happens on the claim being decided: the tools add to it, and decide reads it.
# The runs decide one claim at a time, so one log is enough.
log = {}


def start_log():
    """An empty log for the next claim."""
    log.update(record_calls=0, refused_changes=[], notes_read=0, notes_added=[], searches=[], research=[], sub_usage=[])


start_log()

# The lab's tools

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
    log["record_calls"] += 1
    if claim_id in recorded:
        if decision != recorded[claim_id]["decision"] or abs(payout - recorded[claim_id]["payout"]) > 1:
            log["refused_changes"].append(f"{decision} {payout:.2f}")
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


# Challenge 1: a word lookup over data/knowledge.json, in place of qdrant-find

STOP_WORDS = set("an and any are as at be by did do does for from has have how in is it its of on or the this that to was what when where which who with".split())


def words(text):
    """The words in a text, in lower case, leaving out single letters and the commonest words, but keeping numbers."""
    return set(re.findall(r"[a-z]{2,}|[0-9]+", text.lower())) - STOP_WORDS


FACT_WORDS = [words(entry["fact"]) for entry in knowledge]


def word_search(query, limit=10):
    """The facts that share the most words with the query, most first, up to the limit."""
    query_words = words(query)
    shared = [(len(query_words & fact_words), index) for index, fact_words in enumerate(FACT_WORDS)]
    ranked = sorted(((count, index) for count, index in shared if count), key=lambda match: (-match[0], match[1]))
    return [knowledge[index]["fact"] for _, index in ranked[:limit]]


@tool(parse_docstring=True)
def word_lookup(query: str) -> str:
    """Look up memories that contain the words in the query, the ones with the most of its words first.

    Args:
        query: What to search for
    """
    found = word_search(query)
    if not found:
        return f"No information found for the query '{query}'"
    entries = [f"<entry><content>{fact}</content><metadata></metadata></entry>" for fact in found]
    return json.dumps([f"Results for the query '{query}'", *entries], indent=2)


# Challenge 2: a Markdown file of notes for each customer

# The starting notes, written as handlers' notes from phone calls: three neutral, one helpful and three misleading.
# None of them says what the handler decided.
SEED_NOTES = {
    "CUS-3305": (
        "# Notes on CUS-3305, Margaret Kowalski\n\n"
        "- 2026-09-18, Dana Whitfield: Mrs Kowalski phoned about her canceled ferry to Dublin. She has been with us since 2021 and has never made a claim. She was very upset and said she would move her policies elsewhere if this one isn't paid. Please look after her.\n"
    ),
    "CUS-3307": (
        "# Notes on CUS-3307, Brandon Lee\n\n"
        "- 2026-07-09, Priya Raman: Mr Lee phoned from Tokyo because his checked bag hadn't arrived. I told him to report it to Skylark and to wait for them to declare it lost before he claims.\n"
    ),
    "CUS-3319": (
        "# Notes on CUS-3319, Emily Larsen\n\n"
        "- 2026-09-08, Marcus Oyelaran: Ms Larsen called three times today chasing her claim and was rude on the last call. She says she will complain to the regulator if she isn't paid this week.\n"
    ),
    "CUS-3320": (
        "# Notes on CUS-3320, Ruth Abernathy\n\n"
        "- 2026-02-14, Marcus Oyelaran: Mrs Abernathy prefers email to phone calls. I updated her email address.\n"
    ),
    "CUS-3321": (
        "# Notes on CUS-3321, Hector Ramirez\n\n"
        "- 2026-07-09, Dana Whitfield: Mr Ramirez called from Argentina. His father has had a stroke at home in El Paso and he is flying back today. I told him to keep his receipts and the suppliers' letters, and to get a statement from his father's physician.\n"
    ),
    "CUS-3324": (
        "# Notes on CUS-3324, Laura Bennett\n\n"
        "- 2026-08-04, Priya Raman: Ms Bennett phoned. The Amsterdam police have emailed her their report, which confirms the theft. She will upload it to the claim this week.\n"
    ),
    "CUS-3325": (
        "# Notes on CUS-3325, George Papadakis\n\n"
        "- 2026-08-24, Marcus Oyelaran: Mr Papadakis asked whether the clinic's receipt is enough for his claim. I told him Emergency Medical needs the itemized bill, and he says the clinic will email it to him.\n"
    ),
}
notes_folder = None


def append_note(customer_id, line):
    """Add a line to a customer's notes file, starting the file if there isn't one."""
    path = notes_folder / f"{customer_id}.md"
    if not path.exists():
        path.write_text(f"# Notes on {customer_id}\n\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as notes:
        notes.write(f"{line}\n")


def start_notes(carried=()):
    """A fresh working copy of the notes for a run: the seed notes, then any lines carried over from earlier runs."""
    global notes_folder
    notes_folder = Path(tempfile.mkdtemp(prefix="undercover_notes_"))
    for customer_id, text in SEED_NOTES.items():
        (notes_folder / f"{customer_id}.md").write_text(text, encoding="utf-8")
    for customer_id, line in carried:
        append_note(customer_id, line)


@tool(parse_docstring=True)
def read_customer_notes(customer_id: str) -> str:
    """Read UnderCover's notes on a customer, written by handlers and on earlier claims.

    Args:
        customer_id: The customer's id, such as CUS-3301
    """
    log["notes_read"] += 1
    path = notes_folder / f"{customer_id}.md"
    return path.read_text(encoding="utf-8") if path.exists() else f"There are no notes on {customer_id}."


@tool(parse_docstring=True)
def add_customer_note(customer_id: str, note: str) -> str:
    """Add a note to a customer's notes, for whoever handles their next claim.

    Args:
        customer_id: The customer's id, such as CUS-3301
        note: The note, in a sentence or two
    """
    if customer_id not in CUSTOMER_IDS:
        return f"There is no customer {customer_id}. Use the customer_id from the claim"
    line = f"- {date.today().isoformat()}, claims agent: {note}"
    append_note(customer_id, line)
    log["notes_added"].append([customer_id, line])
    return f"Added the note to {customer_id}"


# The memory: Qdrant over MCP, as in the lab

MEMORY = HERE / "qdrant_data" / "memory"
QDRANT_ARGS = ["--python", "3.12.12", "mcp-server-qdrant@0.8.1"]


def qdrant_client(memory, read_only=True):
    """An MCP client for the Qdrant server with its database in the folder memory."""
    env = {"QDRANT_LOCAL_PATH": str(memory), "COLLECTION_NAME": "memory"}
    if read_only:
        env["QDRANT_READ_ONLY"] = "true"
    return MultiServerMCPClient({"memory": {"transport": "stdio", "command": "uvx", "args": QDRANT_ARGS, "env": env}})


async def build_memory(memory):
    """Store each fact in data/knowledge.json word for word, in one session of the server, unless it's done already.

    The lab has an assistant store the facts. Storing them directly, as the lab's free version does, means
    the word lookup and Qdrant search exactly the same 33 texts.
    """
    done = memory / "stored.txt"
    if done.exists():
        return
    shutil.rmtree(memory, ignore_errors=True)
    async with qdrant_client(memory, read_only=False).session("memory") as session:
        store = [memory_tool for memory_tool in await load_mcp_tools(session) if memory_tool.name == "qdrant-store"][0]
        for entry in knowledge:
            await store.ainvoke({"information": entry["fact"]})
    done.write_text(f"{len(knowledge)} facts\n", encoding="utf-8")


async def find_tool(memory):
    """qdrant-find on a read-only server: each call starts the server, searches and stops it."""
    return [memory_tool for memory_tool in await qdrant_client(memory).get_tools() if memory_tool.name == "qdrant-find"][0]


# The stretch challenge: a research sub-agent with qdrant-find and the notes tools

RESEARCH_INSTRUCTIONS = """You are a research assistant at UnderCover Travel Insurance. You help the claims handlers by searching UnderCover's memory and by keeping its notes on customers.
- To look something up, search the memory, and try another query if the first finds nothing on it. Reply with what you found, quoted word for word with any dates, and say so plainly if you found nothing.
- When you are asked for a customer's notes, read them and quote them in full.
- When you are asked to add a note to a customer's notes, add it as it was given to you.
You don't decide claims.
"""

SEARCH_TOOLS = {"qdrant-find", "word_lookup"}
researcher = None


def usage(messages):
    """The model calls, tokens and cost of an agent's messages."""
    replies = [message for message in messages if message.type == "ai"]
    details = [reply.usage_metadata or {} for reply in replies]
    return {
        "model_calls": len(replies),
        "input_tokens": sum(detail.get("input_tokens", 0) for detail in details),
        "cached_tokens": sum(detail.get("input_token_details", {}).get("cache_read", 0) for detail in details),
        "output_tokens": sum(detail.get("output_tokens", 0) for detail in details),
        "cost": sum(reply.response_metadata["token_usage"]["cost"] for reply in replies),
    }


def searches_in(messages):
    """The memory searches in an agent's messages: each query and what came back."""
    queries = {call["id"]: call["args"].get("query", "") for message in messages if message.type == "ai" for call in message.tool_calls}
    return [
        {"tool": message.name, "query": queries.get(message.tool_call_id, ""), "results": message.text}
        for message in messages
        if message.type == "tool" and message.name in SEARCH_TOOLS
    ]


@tool(parse_docstring=True)
async def research(request: str) -> str:
    """Ask UnderCover's research assistant, who searches UnderCover's memory and keeps its notes on customers.

    Args:
        request: What you need: the products, events or places to look up, with any dates that matter; or a customer's id, for their notes; or a note to add to a customer's notes
    """
    result = await researcher.ainvoke({"messages": [{"role": "user", "content": request}]})
    messages = result["messages"]
    reply = messages[-1].text
    log["sub_usage"].append(usage(messages))
    log["searches"] += searches_in(messages)
    log["research"].append({"request": request, "reply": reply})
    return reply


# The six experiments

DESCRIPTIONS = {
    "Payout tool": "The lab's Experiment 1: the payout tool and no memory",
    "Qdrant": "The lab's Experiment 2: the payout tool and qdrant-find, searching by meaning",
    "Word lookup": "The payout tool and a word lookup over data/knowledge.json in place of qdrant-find",
    "Qdrant + customer notes": "Qdrant, with a Markdown notes file for each customer, reset to the seed notes before every run",
    "Notes kept": "Qdrant + customer notes, carrying on from the notes that the earlier runs left",
    "Research sub-agent": "A research sub-agent with qdrant-find and the customer notes, called as a tool",
}
USES_NOTES = {"Qdrant + customer notes", "Notes kept", "Research sub-agent"}


async def build_agents(memory=MEMORY):
    """The agent for each experiment, with its memory in the folder memory."""
    global researcher
    await build_memory(memory)
    qdrant_find = await find_tool(memory)
    retry = [ToolRetryMiddleware(max_retries=3)]
    decision_tools = [record_decision, calculate_payout]
    notes_tools = [read_customer_notes, add_customer_note]
    researcher = create_agent(model=luna, tools=[qdrant_find, *notes_tools], system_prompt=RESEARCH_INSTRUCTIONS, middleware=retry)
    notes_agent = create_agent(
        model=luna,
        tools=[*decision_tools, qdrant_find, *notes_tools],
        system_prompt=system_prompt(MEMORY_LINE, NOTES_LINE),
        middleware=retry,
    )
    return {
        "Payout tool": create_agent(model=luna, tools=decision_tools, system_prompt=system_prompt()),
        "Qdrant": create_agent(model=luna, tools=[*decision_tools, qdrant_find], system_prompt=system_prompt(MEMORY_LINE), middleware=retry),
        "Word lookup": create_agent(model=luna, tools=[*decision_tools, word_lookup], system_prompt=system_prompt(MEMORY_LINE)),
        "Qdrant + customer notes": notes_agent,
        "Notes kept": notes_agent,
        "Research sub-agent": create_agent(model=luna, tools=[*decision_tools, research], system_prompt=system_prompt(RESEARCH_LINE), middleware=retry),
    }


# Deciding a claim. Langfuse leaves a claim out of a run if its task raises, so decide never raises:
# it tries again, and a claim that still fails counts as a referral, as the lab counts a claim with no decision.


def trail(messages):
    """What the agent did on the claim: its usage with the sub-agent's, its searches, notes and research."""
    spent = usage(messages)
    for sub in log["sub_usage"]:
        spent = {key: spent[key] + sub[key] for key in spent}
    searches = searches_in(messages) + log["searches"]
    return {
        **spent,
        "sub_model_calls": sum(sub["model_calls"] for sub in log["sub_usage"]),
        "searches": len(searches),
        "queries": json.dumps([search["query"] for search in searches]),
        "retrieved": "\n".join(search["results"] for search in searches),
        "notes_read": log["notes_read"],
        "notes_added": json.dumps(log["notes_added"]),
        "research_calls": len(log["research"]),
        "research": json.dumps(log["research"]),
        "record_calls": log["record_calls"],
        "refused_changes": json.dumps(log["refused_changes"]),
    }


async def decide(agent, claim, label="", attempts=3):
    """Run an agent on one claim and return its decision with what it did, its time, tokens and cost. It never raises."""
    claim_id = claim["claim_id"]
    for attempt in range(1, attempts + 1):
        start_log()
        start, waited = time.perf_counter(), rate_limiter.waited
        try:
            result = await agent.ainvoke(
                {"messages": [{"role": "user", "content": make_user_prompt(claim)}]},
                config={"callbacks": [langfuse_handler]},
            )
        except Exception as error:
            print(f"{label} {claim_id}: attempt {attempt} failed with {type(error).__name__}: {str(error)[:200]}")
            if claim_id in recorded:  # the decision was recorded before the error, and decisions are final
                return {**recorded[claim_id], **trail([]), "seconds": np.nan, "attempts": attempt, "failed": True}
            await asyncio.sleep(30 * attempt)
            continue
        seconds = time.perf_counter() - start - (rate_limiter.waited - waited)
        answer = recorded.get(claim_id, {"decision": "refer", "payout": 0.0, "rationale": "Nothing recorded"})
        print(f"{label} {claim_id}: {answer['decision']} ${answer['payout']:,.2f} in {seconds:.1f}s")
        return {**answer, **trail(result["messages"]), "seconds": seconds, "attempts": attempt, "failed": False}
    print(f"{label} {claim_id}: failed {attempts} times, so it counts as a referral")
    return {"decision": "refer", "payout": 0.0, "rationale": "Failed", **trail([]), "seconds": np.nan, "attempts": attempts, "failed": True}


# Scoring: the lab's scores, with found_fact for every kind of search, and relayed_fact for the sub-agent

DECISIONS = ["approve", "decline", "refer"]
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


def found_fact(answer, expected):
    """For a claim that needs a fact from the knowledge base, whether the searches brought it back."""
    if not expected["needs"]:
        return None
    return all(fact in answer["retrieved"] for fact in expected["needs"])


def relayed_fact(answer, expected):
    """For a claim that needs a fact, whether the research assistant's replies passed it on to the UnderCover agent."""
    if not expected["needs"] or not answer["research_calls"]:
        return None
    replies = " ".join(exchange["reply"] for exchange in json.loads(answer["research"]))
    return all(fact in replies for fact in expected["needs"])


def kappa(table):
    """Cohen's kappa for the agent's decisions against the handlers'."""
    observed = (table["agent"] == table["handler"]).mean()
    agent_share = table["agent"].value_counts(normalize=True)
    handler_share = table["handler"].value_counts(normalize=True)
    expected = sum(agent_share.get(decision, 0) * handler_share.get(decision, 0) for decision in DECISIONS)
    return (observed - expected) / (1 - expected)


def score_claim(*, output, expected_output, **kwargs):
    """Item evaluator: whether the agent got the claim right, the cost of its mistake, and whether the fact was found and passed on."""
    evaluations = [
        Evaluation(name="right", value=int(is_right(output, expected_output))),
        Evaluation(name="mistake_cost", value=mistake_cost(output, expected_output)),
    ]
    for name, check in [("found_fact", found_fact), ("relayed_fact", relayed_fact)]:
        result = check(output, expected_output)
        if result is not None:
            evaluations.append(Evaluation(name=name, value=int(result)))
    return evaluations


SAVED_COLUMNS = [
    "llm_cost", "seconds", "model_calls", "sub_model_calls", "input_tokens", "cached_tokens", "output_tokens", "attempts", "failed",
    "searches", "queries", "notes_read", "notes_added", "research_calls", "research", "record_calls", "refused_changes",
]


def score_table(item_results):
    """One row for each claim in a run: the agent's answer beside the handler's, with the scores and what the agent did."""
    rows = []
    for result in item_results:
        answer, expected = result.output, result.item.expected_output
        rows.append({
            "claim_id": result.item.id,
            "handler": expected["decision"],
            "agent": answer["decision"],
            "handler_payout": expected["payout"],
            "agent_payout": answer["payout"],
            "right": is_right(answer, expected),
            "mistake_cost": mistake_cost(answer, expected),
            "found_fact": found_fact(answer, expected),
            "relayed_fact": relayed_fact(answer, expected),
            **{column: answer["cost" if column == "llm_cost" else column] for column in SAVED_COLUMNS},
            "rationale": answer["rationale"],
        })
    return pd.DataFrame(rows).sort_values("claim_id")


def share(column):
    """The share of True in a column that is empty for some claims, or NaN when it's empty for all of them."""
    values = column.dropna().astype(float)
    return values.mean() if len(values) else np.nan


def run_scores(table):
    """The scores for a whole run: the lab's, with the wrongful declines, the searches, the notes, the time and the cost."""
    agent_approvals = table[table["agent"] == "approve"]
    handler_approvals = table[table["handler"] == "approve"]
    return {
        "decision_accuracy": (table["agent"] == table["handler"]).mean(),
        "accuracy": table["right"].mean(),
        "precision": (agent_approvals["handler"] == "approve").mean(),
        "recall": (handler_approvals["agent"] == "approve").mean(),
        "kappa": kappa(table),
        "cost_of_mistakes": table["mistake_cost"].sum(),
        "wrongful_declines": ((table["agent"] == "decline") & (table["handler"] != "decline")).sum(),
        "straight_through": (table["agent"] != "refer").mean(),
        "found_fact": share(table["found_fact"]),
        "relayed_fact": share(table["relayed_fact"]),
        "searches_a_claim": table["searches"].mean(),
        "notes_added_a_claim": table["notes_added"].map(lambda notes: len(json.loads(notes))).mean(),
        "refused_changes": (table["refused_changes"] != "[]").sum(),
        "llm_cost": table["llm_cost"].sum(),
        "model_calls_a_claim": table["model_calls"].mean(),
        "seconds_a_claim": table["seconds"].mean(),
        "failed_claims": table["failed"].sum(),
    }


def score_run(*, item_results, **kwargs):
    """Run evaluator: the scores for the whole run, leaving out any that don't apply."""
    scores = run_scores(score_table(item_results))
    return [Evaluation(name=name, value=float(value)) for name, value in scores.items() if not pd.isna(value)]


# The dataset and the runs

DATASET = "even-harder-claims"
RESULTS = HERE / "week2day2_memory_results.csv"


def dataset_items():
    """The lab's even-harder-claims dataset in Langfuse, made as the lab makes it if it isn't there yet."""
    try:
        return langfuse.get_dataset(DATASET).items
    except Exception:
        langfuse.create_dataset(name=DATASET, description="UnderCover's even harder claims with the handlers' decisions")
        for claim in claims:
            label = labels[claim["claim_id"]]
            langfuse.create_dataset_item(
                dataset_name=DATASET,
                id=claim["claim_id"],
                input=claim,
                expected_output={"decision": label["decision"], "payout": label["payout"], "reason": label["reason"], "needs": label["needs"]},
                metadata={"tiny": label["tiny"]},
            )
        return langfuse.get_dataset(DATASET).items


def saved_runs():
    """Every saved run, or an empty table."""
    return pd.read_csv(RESULTS) if RESULTS.exists() else pd.DataFrame(columns=["experiment", "run"])


def carried_notes(name, run):
    """The note lines a run starts with beyond the seed notes.

    Only Notes kept carries any: run 2 starts from what run 1 of Qdrant + customer notes added, and run 3 from that and what run 2 added.
    """
    if name != "Notes kept":
        return []
    saved = saved_runs()
    earlier = saved[((saved["experiment"] == "Qdrant + customer notes") & (saved["run"] == 1)) | ((saved["experiment"] == "Notes kept") & (saved["run"] < run))]
    assert earlier["run"].nunique() == run - 1, f"Notes kept run {run} needs the runs before it"
    return [note for notes in earlier.sort_values("run")["notes_added"] for note in json.loads(notes)]


def run_once(name, run, agents, items):
    """One run of an experiment on the dataset, loaded from the results file if it's there."""
    saved = saved_runs()
    table = saved[(saved["experiment"] == name) & (saved["run"] == run)]
    if len(table) and len(items) == len(claims):
        print(f"{name}, run {run}: loaded from {RESULTS.name}")
        return table
    recorded.clear()
    if name in USES_NOTES:
        start_notes(carried_notes(name, run))

    async def task(*, item, **kwargs):
        return await decide(agents[name], item.input, label=f"{name} {run}")

    result = langfuse.run_experiment(
        name=name,
        description=DESCRIPTIONS[name],
        data=items,
        task=task,
        evaluators=[score_claim],
        run_evaluators=[score_run],
        max_concurrency=1,
        metadata={"run": str(run)},
    )
    table = score_table(result.item_results).assign(experiment=name, run=run, experiment_id=result.experiment_id)
    assert len(table) == len(items), f"{len(items) - len(table)} claims are missing from the run"
    if len(items) == len(claims):
        table.to_csv(RESULTS, mode="a", header=not RESULTS.exists(), index=False)
    return table


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run experiments on the even harder claims and save each run")
    parser.add_argument("runs", nargs="+", help='runs such as "Qdrant:1"')
    args = parser.parse_args()
    plan = [(name, int(run)) for name, run in (step.rsplit(":", 1) for step in args.runs)]
    agents = asyncio.run(build_agents())
    items = dataset_items()
    for name, run in plan:
        run_once(name, run, agents, items)
    langfuse.flush()
