"""Commercial assignment: concurrent loan application classification and decisioning.

An EDUCATIONAL PROTOTYPE on SYNTHETIC data, not a production lending system. See README.md
for fairness considerations, the model's limitations and why a person reviews every referral.

A lender scores a batch of loan applications overnight. Each application is an independent job,
the same shape as the lab's dispatcher: a dispatcher fans out one worker per application, each
worker predicts the probability of default with a Random Forest and applies the lending policy,
and an aggregate node fans back in to measure the batch. No LLM is involved.

    uv run --with scikit-learn python loan_swarm.py
    uv run --with scikit-learn python loan_swarm.py --applications 3000 --latency 0.05 --langfuse
"""

import argparse
import json
import operator
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, TypedDict

import numpy as np
import pandas as pd
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy, Send
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split

FEATURES = [
    "annual_income",
    "loan_amount",
    "loan_to_income",
    "credit_history_years",
    "debt_to_income",
    "late_payments_12m",
    "prior_defaults",
    "on_time_payment_rate",
]
RESULTS = Path(__file__).resolve().parent / "results"
CONCURRENCY_LEVELS = (3, 5, 10)


# Synthetic data


def make_applications(count: int = 2000, seed: int = 7) -> pd.DataFrame:
    """Generate synthetic loan applications with a default label.

    The default label comes from a known logistic risk function of the features, plus noise,
    so the model has real signal to find. `applicant_group` is a synthetic stand-in for a
    protected characteristic: the model never sees it, but it is correlated with income, so
    the fairness audit can show how a proxy carries disparity into the decisions."""
    rng = np.random.default_rng(seed)
    group = rng.choice(["A", "B"], size=count, p=[0.6, 0.4])
    income = rng.lognormal(mean=np.where(group == "A", 11.0, 10.8), sigma=0.45).round(-2)
    loan_amount = (income * rng.uniform(0.05, 0.9, count)).round(-2)
    history = rng.gamma(shape=2.5, scale=3.5, size=count).round(1)
    debt_to_income = rng.beta(2.2, 5.0, count).round(3)
    late = rng.poisson(lam=np.clip(1.5 - history / 10, 0.2, None))
    prior_defaults = rng.binomial(1, 0.07, count)
    on_time = np.clip(1 - late / 14 - rng.uniform(0, 0.08, count), 0, 1).round(3)

    loan_to_income = loan_amount / income
    logit = (
        -3.0
        + 3.2 * debt_to_income
        + 1.8 * loan_to_income
        + 0.45 * late
        + 1.6 * prior_defaults
        - 0.07 * history
        - 2.0 * (on_time - 0.9)
        - 0.4 * (np.log(income) - 10.9)
        + rng.normal(0, 0.6, count)
    )
    defaulted = rng.random(count) < 1 / (1 + np.exp(-logit))
    return pd.DataFrame(
        {
            "application_id": [f"APP-{index + 1:05d}" for index in range(count)],
            "applicant_group": group,
            "annual_income": income,
            "loan_amount": loan_amount,
            "loan_to_income": loan_to_income.round(4),
            "credit_history_years": history,
            "debt_to_income": debt_to_income,
            "late_payments_12m": late,
            "prior_defaults": prior_defaults,
            "on_time_payment_rate": on_time,
            "defaulted": defaulted.astype(int),
        }
    )


def split(applications: pd.DataFrame, seed: int = 7) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Separate training and held-out test sets, stratified on the default label."""
    train, test = train_test_split(applications, test_size=0.25, stratify=applications["defaulted"], random_state=seed)
    return train.reset_index(drop=True), test.reset_index(drop=True)


def train_model(train: pd.DataFrame, seed: int = 7) -> RandomForestClassifier:
    """Fit the Random Forest on the training set only. n_jobs=1 keeps each prediction on its worker's thread."""
    model = RandomForestClassifier(
        n_estimators=200, max_depth=8, min_samples_leaf=10, class_weight="balanced", random_state=seed, n_jobs=1
    )
    model.fit(train[FEATURES], train["defaulted"])
    return model


# The lending policy


@dataclass(frozen=True)
class LendingPolicy:
    """The lender's rules. Every threshold is configurable; these defaults are illustrative only."""

    decline_probability: float = 0.60  # decline when the model's default risk is at least this
    approve_probability: float = 0.25  # approve only below this, and only if every rule below passes
    max_debt_to_income: float = 0.45  # above this, never approve automatically
    hard_decline_debt_to_income: float = 0.65  # above this, decline whatever the model says
    max_loan_to_income: float = 0.60
    large_loan_amount: float = 60_000  # a person reviews every loan at least this large
    min_history_years: float = 1.0  # too little history for the model to be trusted


def decide(application: dict, probability: float, policy: LendingPolicy) -> tuple[str, list[str]]:
    """Apply the policy to one application and its default probability. Return the decision and the reasons."""
    reasons = []
    if application["debt_to_income"] > policy.hard_decline_debt_to_income:
        return "decline", [
            f"Debt-to-income {application['debt_to_income']:.0%} is above the hard limit of {policy.hard_decline_debt_to_income:.0%}"
        ]
    if probability >= policy.decline_probability:
        return "decline", [f"Predicted default risk {probability:.0%} is at or above {policy.decline_probability:.0%}"]

    if probability >= policy.approve_probability:
        reasons.append(
            f"Predicted default risk {probability:.0%} is between {policy.approve_probability:.0%} and {policy.decline_probability:.0%}"
        )
    if application["debt_to_income"] > policy.max_debt_to_income:
        reasons.append(f"Debt-to-income {application['debt_to_income']:.0%} is above {policy.max_debt_to_income:.0%}")
    if application["loan_to_income"] > policy.max_loan_to_income:
        reasons.append(f"Loan is {application['loan_to_income']:.0%} of income, above {policy.max_loan_to_income:.0%}")
    if application["prior_defaults"]:
        reasons.append("A prior default is on record")
    if application["loan_amount"] >= policy.large_loan_amount:
        reasons.append(
            f"Loan of ${application['loan_amount']:,.0f} needs a person's review at ${policy.large_loan_amount:,.0f} or more"
        )
    if application["credit_history_years"] < policy.min_history_years:
        reasons.append(f"Only {application['credit_history_years']} years of credit history")
    if reasons:
        return "refer", reasons
    return "approve", [
        f"Predicted default risk {probability:.0%} is below {policy.approve_probability:.0%} and every policy rule passes"
    ]


def assess(application: dict, model: RandomForestClassifier, policy: LendingPolicy) -> dict:
    """One worker's job: predict, decide and explain."""
    row = pd.DataFrame([application])[FEATURES]
    probability = float(model.predict_proba(row)[0, 1])
    decision, reasons = decide(application, probability, policy)
    return {
        "application_id": application["application_id"],
        "default_probability": round(probability, 6),
        "predicted_default": int(probability >= 0.5),
        "decision": decision,
        "reasons": reasons,
    }


# Measuring a batch


def classification_metrics(actual: list[int], predicted: list[int], probabilities: list[float]) -> dict:
    """The model's classification against the held-out default labels (positive class: defaulted)."""
    matrix = confusion_matrix(actual, predicted, labels=[0, 1])
    return {
        "accuracy": round(float(accuracy_score(actual, predicted)), 4),
        "precision": round(float(precision_score(actual, predicted, zero_division=0)), 4),
        "recall": round(float(recall_score(actual, predicted, zero_division=0)), 4),
        "f1": round(float(f1_score(actual, predicted, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(actual, probabilities)), 4),
        "confusion_matrix": {
            "true_negative": int(matrix[0, 0]),
            "false_positive": int(matrix[0, 1]),
            "false_negative": int(matrix[1, 0]),
            "true_positive": int(matrix[1, 1]),
        },
    }


def summarise(assessments: list[dict], applications: pd.DataFrame) -> dict:
    """Fan-in: the batch's completeness, the model's metrics, the decisions and the fairness audit."""
    table = pd.DataFrame(assessments).merge(applications, on="application_id", how="left", validate="many_to_one")
    expected = set(applications["application_id"])
    decisions = table["decision"].value_counts().reindex(["approve", "refer", "decline"], fill_value=0)
    default_rate = table.groupby("decision")["defaulted"].mean().reindex(["approve", "refer", "decline"])
    by_group = table.groupby("applicant_group").agg(
        applications=("decision", "size"),
        approval_rate=("decision", lambda d: (d == "approve").mean()),
        decline_rate=("decision", lambda d: (d == "decline").mean()),
        actual_default_rate=("defaulted", "mean"),
    )
    approval = by_group["approval_rate"]
    return {
        "applications": len(table),
        "missing": sorted(expected - set(table["application_id"])),
        "duplicates": int(table["application_id"].duplicated().sum()),
        "model": classification_metrics(
            table["defaulted"].tolist(), table["predicted_default"].tolist(), table["default_probability"].tolist()
        ),
        "decisions": {name: int(count) for name, count in decisions.items()},
        "default_rate_by_decision": {
            name: (None if pd.isna(rate) else round(float(rate), 4)) for name, rate in default_rate.items()
        },
        "fairness": {
            "by_group": json.loads(by_group.round(4).to_json(orient="index")),
            "approval_rate_ratio": round(float(approval.min() / approval.max()), 4) if approval.max() > 0 else None,
        },
    }


# The LangGraph dispatcher


class Batch(TypedDict, total=False):
    """What the dispatcher keeps for one batch."""

    application_ids: list[str]
    assessments: Annotated[list, operator.add]
    summary: dict


def build_graph(applications: pd.DataFrame, model: RandomForestClassifier, policy: LendingPolicy, latency: float = 0.0):
    """Compile dispatch -> assess_application (one per application) -> aggregate.

    latency stands in for the credit bureau lookup each application needs, the I/O wait
    where a real decisioning batch spends much of its time."""
    records = {record["application_id"]: record for record in applications.to_dict("records")}

    def dispatch(state: Batch) -> dict:
        return {"application_ids": list(records)}

    def fan_out(state: Batch) -> list[Send]:
        return [Send("assess_application", application_id) for application_id in state["application_ids"]]

    def assess_application(application_id: str) -> dict:
        started = datetime.now()
        time.sleep(latency)
        result = assess(records[application_id], model, policy)
        return {"assessments": [{**result, "started": started, "finished": datetime.now()}]}

    def aggregate(state: Batch) -> dict:
        return {"summary": summarise(state["assessments"], applications)}

    builder = StateGraph(Batch)
    builder.add_node("dispatch", dispatch)
    builder.add_node("assess_application", assess_application, retry_policy=RetryPolicy(max_attempts=3))
    builder.add_node("aggregate", aggregate)
    builder.add_edge(START, "dispatch")
    builder.add_conditional_edges("dispatch", fan_out, ["assess_application"])
    builder.add_edge("assess_application", "aggregate")
    builder.add_edge("aggregate", END)
    return builder.compile()


def run_sequential(
    applications: pd.DataFrame, model: RandomForestClassifier, policy: LendingPolicy, latency: float = 0.0
) -> tuple[list[dict], dict, float]:
    """The baseline: a plain loop over the applications, one after another."""
    started = time.perf_counter()
    assessments = []
    for application in applications.to_dict("records"):
        time.sleep(latency)
        assessments.append(assess(application, model, policy))
    return assessments, summarise(assessments, applications), time.perf_counter() - started


def peak_overlap(assessments: list[dict]) -> int:
    """The most workers that were running at the same moment."""
    events = sorted([(a["started"], 1) for a in assessments] + [(a["finished"], -1) for a in assessments])
    running = peak = 0
    for _, change in events:
        running += change
        peak = max(peak, running)
    return peak


def fingerprint(assessments: list[dict]) -> list[tuple]:
    """What must be identical across concurrency levels: each application's probability, decision and reasons."""
    return sorted(
        (a["application_id"], a["default_probability"], a["decision"], tuple(a["reasons"])) for a in assessments
    )


def langfuse_config(run_name: str, session_id: str) -> tuple[dict, Any]:
    """Langfuse tracing for a graph run, when the keys are set."""
    if not os.getenv("LANGFUSE_PUBLIC_KEY"):
        return {}, None
    from langfuse.langchain import CallbackHandler

    handler = CallbackHandler()
    return {"callbacks": [handler], "run_name": run_name, "metadata": {"langfuse_session_id": session_id}}, handler


def compare(
    applications: pd.DataFrame,
    model: RandomForestClassifier,
    policy: LendingPolicy,
    latency: float,
    levels=CONCURRENCY_LEVELS,
    trace: bool = False,
) -> dict:
    """Time the batch sequentially and at each concurrency level, and check every run made the same decisions."""
    baseline, baseline_summary, baseline_seconds = run_sequential(applications, model, policy, latency)
    expected = fingerprint(baseline)
    rows = [
        {
            "mode": "sequential loop",
            "workers": 1,
            "seconds": round(baseline_seconds, 3),
            "peak_overlap": 1,
            "speedup": 1.0,
            "consistent": True,
        }
    ]
    graph = build_graph(applications, model, policy, latency)
    session_id = f"loan-batch {datetime.now():%Y%m%d-%H%M%S}"
    langfuse = None
    for workers in levels:
        config, handler = langfuse_config(f"Loan batch, {workers} workers", session_id) if trace else ({}, None)
        started = time.perf_counter()
        state = graph.invoke({}, {**config, "max_concurrency": workers})
        seconds = time.perf_counter() - started
        consistent = fingerprint(state["assessments"]) == expected and state["summary"] == baseline_summary
        rows.append(
            {
                "mode": "LangGraph",
                "workers": workers,
                "seconds": round(seconds, 3),
                "peak_overlap": peak_overlap(state["assessments"]),
                "speedup": round(baseline_seconds / seconds, 2),
                "consistent": consistent,
            }
        )
        if handler:
            from langfuse import get_client

            langfuse = get_client()
            model_metrics = state["summary"]["model"]
            for name in ("accuracy", "precision", "recall", "f1", "roc_auc"):
                langfuse.create_score(trace_id=handler.last_trace_id, name=name, value=model_metrics[name])
            langfuse.create_score(trace_id=handler.last_trace_id, name="seconds", value=seconds)
            langfuse.create_score(trace_id=handler.last_trace_id, name="consistent", value=float(consistent))
    if langfuse:
        langfuse.flush()
    return {"timings": rows, "summary": baseline_summary, "langfuse_session": session_id if langfuse else None}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Concurrent loan decisioning on synthetic data (educational prototype)"
    )
    parser.add_argument(
        "--applications", type=int, default=2000, help="total synthetic applications; 25%% are held out and decided"
    )
    parser.add_argument(
        "--latency", type=float, default=0.05, help="seconds for each application's credit bureau lookup"
    )
    parser.add_argument("--langfuse", action="store_true", help="trace the graph runs and their scores in Langfuse")
    args = parser.parse_args()
    if args.langfuse:
        from dotenv import load_dotenv

        load_dotenv(Path(__file__).resolve().parents[3] / ".env", override=True)

    applications = make_applications(args.applications)
    train, test = split(applications)
    model = train_model(train)
    policy = LendingPolicy()
    print(f"Trained on {len(train)} applications, deciding the {len(test)} held-out ones\n")

    report = {"applications": args.applications, "train": len(train), "test": len(test), "policy": asdict(policy)}
    for latency in (0.0, args.latency):
        result = compare(test, model, policy, latency, trace=args.langfuse and latency > 0)
        report[f"latency_{latency}"] = result
        print(f"Bureau lookup latency {latency}s:")
        print(pd.DataFrame(result["timings"]).to_string(index=False), "\n")

    summary = report[f"latency_{args.latency}"]["summary"]
    print(json.dumps(summary, indent=2))
    if report[f"latency_{args.latency}"]["langfuse_session"]:
        print(f"\nLangfuse session: {report[f'latency_{args.latency}']['langfuse_session']}")
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "loan_run.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nSaved {RESULTS / 'loan_run.json'}")


if __name__ == "__main__":
    main()
