"""Compare saved Day 1 runs offline; use --run to repeat the concise experiment."""

import argparse
import json
import os
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from time import perf_counter
from typing import Literal

import pandas as pd
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.runnables import Runnable
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langfuse import Evaluation, Langfuse, get_client
from langfuse.api import DatasetItem
from langfuse.experiment import ExperimentItemResult
from langfuse.langchain import CallbackHandler

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))  # lets the script run directly as well as with -m

from labs.week2day1_payout import Benefit, Line, Payout, work_out_payout  # noqa: E402
SNAPSHOT = HERE / "comparison_runs.csv"
RESULTS = HERE / "results"
CONCISE = "Concise wording + payout tool"
FULL = "Full wording + payout tool"
MODEL = "openai/gpt-6-luna"
CLAIM_IDS = {f"CLM-{number}" for number in range(1201, 1226)}
PENALTIES = [0, 500, 1500, 5000, 10000]
DEFAULT_PENALTY = 1500
REFERRAL_COST = 50

INSTRUCTIONS = (
    "You are a claims handler at UnderCover Travel Insurance.\n"
    "Decide the claim you are given, using the policy wording below and"
    " the customer's policy record.\n"
    "\n"
    "Choose one decision:\n"
    "- approve: the wording covers the claim and the required documents"
    " are attached. Work out the payout using section 10.\n"
    "- decline: the wording does not cover the claim.\n"
    "- refer: a colleague needs to look at it, because a required "
    "document is missing, or the story and the documents disagree, or "
    "the wording does not settle the question.\n"
    "\n"
    "Use your tools to record your decision.\n"
)
PAYOUT_INSTRUCTION = (
    "Use the payout tool to work out the payout on an approved claim, "
    "and record the payout it returns.\n"
)


@dataclass(frozen=True)
class Decision:
    decision: Literal["approve", "decline", "refer"]
    payout: float
    rationale: str


def mistake_cost(answer: Decision, expected: Decision, penalty: float) -> float:
    """Score a fixed prediction with the lab's business cost matrix."""
    if answer.decision == expected.decision:
        return (
            abs(answer.payout - expected.payout) if answer.decision == "approve" else 0
        )
    if answer.decision == "decline":
        return penalty
    if answer.decision == "approve":
        return answer.payout
    return REFERRAL_COST


def comparison(runs: pd.DataFrame, penalty: float) -> pd.DataFrame:
    """Calculate fresh costs from the fixed non-decline costs and decline counts."""
    scored = runs.assign(
        mistake_cost=runs.other_mistake_cost + penalty * runs.wrongful_declines
    )
    return (
        scored.groupby("experiment", sort=False)
        .mean(numeric_only=True)
        .drop(columns="run")
    )


def report(runs: pd.DataFrame) -> None:
    """Display the comparison and how the wording choice changes with the penalty."""
    columns = [
        "accuracy",
        "decision_accuracy",
        "mistake_cost",
        "llm_cost",
        "mean_agent_seconds",
        "mean_input_tokens",
    ]
    print(
        "Mean costs per 25-claim run; seconds/tokens per claim; accuracy is a fraction."
    )
    print(comparison(runs, DEFAULT_PENALTY)[columns].round(6).to_string())
    scenarios = pd.DataFrame(
        {penalty: comparison(runs, penalty).mistake_cost for penalty in PENALTIES}
    ).T
    scenarios.index.name = "wrongful_decline_penalty"
    print("\nBusiness mistake costs with fixed predictions:")
    print(scenarios.round(2).to_string())
    totals = (
        runs.groupby("experiment", sort=False)[
            ["other_mistake_cost", "wrongful_declines"]
        ]
        .sum()
        .astype(float)
    )
    costs, declines = totals["other_mistake_cost"], totals["wrongful_declines"]
    difference = declines[FULL] - declines[CONCISE]
    if difference:
        crossing = (costs[CONCISE] - costs[FULL]) / difference
        print(
            f"\nBreak-even penalty: ${crossing:,.2f}"
            if crossing >= 0
            else "\nNo nonnegative break-even penalty."
        )
    else:
        print(
            "\nEqual wrongful-decline counts: "
            "no change in cost ranking as this penalty varies."
        )


def trace_seconds(client: Langfuse, trace_ids: list[str]) -> list[float]:
    """Read the same whole-agent LangGraph spans as the historical measurements."""
    query = json.dumps(
        [
            {
                "type": "stringOptions",
                "column": "traceId",
                "operator": "any of",
                "value": trace_ids,
            }
        ]
    )
    observations, cursor = [], None
    while True:
        page = client.api.observations.get_many(
            fields="core,basic", filter=query, limit=1000, cursor=cursor
        )
        observations.extend(page.data)
        cursor = page.meta.cursor
        if not cursor:
            break
    durations = []
    for trace_id in trace_ids:
        graphs = [
            o
            for o in observations
            if o.trace_id == trace_id
            and o.name == "LangGraph"
            and o.end_time is not None
        ]
        if len(graphs) != 1:
            raise RuntimeError(
                "Trace data is not complete yet. Rerun --run later; "
                "completed runs are cached."
            )
        durations.append((graphs[0].end_time - graphs[0].start_time).total_seconds())
    return durations


@dataclass
class RunContext:
    client: Langfuse
    items: list[DatasetItem]
    task: Callable
    recorded: dict[str, Decision]
    wording_hash: str


def make_agent(policies: dict, wording: str, recorded: dict[str, Decision]) -> Runnable:
    """Use the original tool schemas and change only the policy wording."""

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
            rationale: 2-3 sentences to explain the decision along with the
                relevant section of the policy
            decision: The decision on the claim
            payout: The amount to pay in US dollars, or 0 for a decline or a referral
        """
        if claim_id in recorded:
            return (
                f"A decision is already recorded on {claim_id}, and decisions are final"
            )
        if decision == "approve" and payout <= 0:
            return "An approval needs a payout above zero"
        recorded[claim_id] = Decision(decision, payout, rationale)
        return f"Recorded {decision} on {claim_id}"

    @tool(parse_docstring=True)
    def calculate_payout(
        policy_id: str, benefit: Benefit, lines: list[Line], paid_by_others: float = 0.0
    ) -> Payout:
        """Work out the payout on an approved claim with UnderCover's payout rules.

        Args:
            policy_id: The customer's policy id
            benefit: The benefit the claim is paid under
            lines: The covered items and expenses, one for each line of the claim,
                with any excluded ones left out. A pair or a set counts as one item
            paid_by_others: Anything a carrier, hotel or other party has paid or
                refunded for the same loss

        Returns:
            The calculation, the payout and whether it needs sign-off
        """
        return work_out_payout(policies[policy_id], benefit, lines, paid_by_others)

    model = ChatOpenAI(
        model=MODEL,
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY"),
        reasoning_effort="none",
        timeout=120,
        max_retries=5,
    )
    instructions = INSTRUCTIONS.replace(
        "using section 10.", "using the Payment section."
    )
    agent = create_agent(
        model=model,
        tools=[record_decision, calculate_payout],
        system_prompt=f"{instructions}{PAYOUT_INSTRUCTION}\n{wording}\n",
    )
    return agent


def make_task(
    agent: Runnable,
    policies: dict,
    recorded: dict[str, Decision],
    handler: CallbackHandler,
) -> Callable:
    """Keep complete policy/claim evidence and aggregate every model message."""

    def task(*, item: DatasetItem, **kwargs: object) -> dict:
        claim = item.input
        prompt = (
            f"# Policy record\n\n{json.dumps(policies[claim['policy_id']], indent=2)}"
            f"\n\n# Claim\n\n{json.dumps(claim, indent=2)}\n"
        )
        start = perf_counter()
        response = agent.invoke(
            {"messages": [{"role": "user", "content": prompt}]},
            config={"callbacks": [handler]},
        )
        elapsed = perf_counter() - start
        answer = recorded.get(
            claim["claim_id"], Decision("refer", 0, "Nothing recorded")
        )
        usages = [
            m.response_metadata["token_usage"]
            for m in response["messages"]
            if m.type == "ai"
        ]
        return {
            **asdict(answer),
            "cost": sum(u["cost"] for u in usages),
            "local_seconds": elapsed,
            "input_tokens": sum(u["prompt_tokens"] for u in usages),
        }

    return task


def item_scores(
    *, output: dict, expected_output: dict, **kwargs: object
) -> list[Evaluation]:
    answer = Decision(output["decision"], output["payout"], output["rationale"])
    expected = Decision(expected_output["decision"], expected_output["payout"], "")
    right = (
        answer.decision == expected.decision
        and abs(answer.payout - expected.payout) <= 1
    )
    return [
        Evaluation(name="right", value=int(right)),
        Evaluation(
            name="mistake_cost",
            value=mistake_cost(answer, expected, DEFAULT_PENALTY),
        ),
    ]


def result_table(results: list[ExperimentItemResult]) -> pd.DataFrame:
    """Reject failed items before a run can enter the comparison."""
    rows = []
    for result in results:
        output, expected_output = result.output, result.item.expected_output
        if output is None:
            raise RuntimeError(
                "Incomplete experiment; inspect its Langfuse trace before retrying."
            )
        answer = Decision(output["decision"], output["payout"], output["rationale"])
        expected = Decision(expected_output["decision"], expected_output["payout"], "")
        same = answer.decision == expected.decision
        rows.append(
            {
                "claim_id": result.item.id,
                "trace_id": result.trace_id,
                **output,
                "right": same and abs(answer.payout - expected.payout) <= 1,
                "decision_right": same,
                "other_mistake_cost": mistake_cost(answer, expected, 0),
                "wrongful_decline": not same and answer.decision == "decline",
            }
        )
    return pd.DataFrame(rows)


def cached_run(context: RunContext, run: int) -> pd.DataFrame:
    """Save predictions before reading traces, so retries need no model calls."""
    path = RESULTS / f"concise_{run}.json"
    if path.exists():
        saved = json.loads(path.read_text(encoding="utf-8"))
        if saved["wording_sha256"] != context.wording_hash or saved["model"] != MODEL:
            raise ValueError(
                "Cached configuration differs; "
                "rename results/ before a fresh experiment."
            )
        table = pd.DataFrame(saved["rows"])
    else:
        context.recorded.clear()
        experiment = context.client.run_experiment(
            name=CONCISE,
            data=context.items,
            task=context.task,
            evaluators=[item_scores],
            run_evaluators=[run_scores],
            max_concurrency=1,
            metadata={
                "wording_sha256": context.wording_hash,
                "model": MODEL,
                "reasoning": "none",
            },
        )
        context.client.flush()
        table = result_table(experiment.item_results)
        saved = {
            "model": MODEL,
            "wording_sha256": context.wording_hash,
            "experiment_id": experiment.experiment_id,
            "rows": table.to_dict(orient="records"),
        }
        path.write_text(json.dumps(saved, indent=2), encoding="utf-8")
    if (
        len(table) != len(CLAIM_IDS)
        or set(table.claim_id) != CLAIM_IDS
        or table.claim_id.duplicated().any()
    ):
        raise ValueError("A comparison requires 25 complete, unique claim results.")
    if "agent_seconds" not in table:
        table["agent_seconds"] = trace_seconds(context.client, table.trace_id.tolist())
        saved["rows"] = table.to_dict(orient="records")
        path.write_text(json.dumps(saved, indent=2), encoding="utf-8")
    return table


def run_scores(
    *, item_results: list[ExperimentItemResult], **kwargs: object
) -> list[Evaluation]:
    """Expose comparable quality and cost scores on the new Langfuse run."""
    table = result_table(item_results)
    declines = table.wrongful_decline.sum()
    values = {
        "accuracy": table.right.mean(),
        "decision_accuracy": table.decision_right.mean(),
        "cost_of_mistakes": table.other_mistake_cost.sum() + DEFAULT_PENALTY * declines,
        "wrongful_declines": declines,
        "llm_cost": table.cost.sum(),
    }
    return [Evaluation(name=name, value=float(value)) for name, value in values.items()]


def run_concise() -> pd.DataFrame:
    """Repeat three concise runs against the original lab's existing dataset."""
    load_dotenv(ROOT / ".env", override=True)
    policies = {
        p["policy_id"]: p
        for p in json.loads(
            (ROOT / "data/evals/harder/policies.json").read_text(encoding="utf-8")
        )
    }
    wording = (ROOT / "data/policy_wording_short.md").read_text(encoding="utf-8")
    wording_hash = sha256(wording.encode()).hexdigest()
    recorded: dict[str, Decision] = {}
    client = get_client()
    agent = make_agent(policies, wording, recorded)
    task = make_task(agent, policies, recorded, CallbackHandler())
    summaries = []
    RESULTS.mkdir(exist_ok=True)
    try:
        dataset = client.get_dataset("harder-claims")
        if (
            len(dataset.items) != len(CLAIM_IDS)
            or {item.id for item in dataset.items} != CLAIM_IDS
        ):
            raise ValueError(
                "Complete Part 4 of the original lab: expected 25 harder claims."
            )
        context = RunContext(client, dataset.items, task, recorded, wording_hash)
        for run in range(1, 4):
            table = cached_run(context, run)
            path = RESULTS / f"concise_{run}.json"
            summaries.append(
                {
                    "experiment": CONCISE,
                    "run": run,
                    "accuracy": table.right.mean(),
                    "decision_accuracy": table.decision_right.mean(),
                    "other_mistake_cost": table.other_mistake_cost.sum(),
                    "wrongful_declines": table.wrongful_decline.sum(),
                    "llm_cost": table.cost.sum(),
                    "mean_agent_seconds": table.agent_seconds.mean(),
                    "mean_input_tokens": table.input_tokens.mean(),
                }
            )
            print(
                f"Concise run {run}: {table.right.sum()}/25 correct; saved {path.name}"
            )
    finally:
        client.shutdown()
    return pd.DataFrame(summaries)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run",
        action="store_true",
        help="Run/resume three paid concise-wording experiments in Langfuse",
    )
    args = parser.parse_args()
    generated = RESULTS / "comparison_runs.csv"
    if args.run:
        historical = pd.read_csv(SNAPSHOT)
        runs = pd.concat(
            [historical[historical.experiment != CONCISE], run_concise()],
            ignore_index=True,
        )
        runs.to_csv(generated, index=False)
    else:
        runs = pd.read_csv(generated if generated.exists() else SNAPSHOT)
    report(runs)


if __name__ == "__main__":
    main()
