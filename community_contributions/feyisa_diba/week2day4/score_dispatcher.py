"""Technical challenge: the lab's dispatcher, with a score_run node after work_claim.

The lab's dispatcher fans out to the claim agents but never comes back together, so the run is
scored outside the graph. Here every work_claim task leads to score_run. LangGraph runs all the
work_claim tasks in one superstep and score_run once, in the next superstep, after every claim
agent has finished, so the scores live in the graph's state with the results.

The workers here are stand-ins, so this costs no model requests:

    uv run python community_contributions/feyisa_diba/week2day4/score_dispatcher.py
"""

import json
import operator
import time
from collections.abc import Callable, Iterable
from datetime import datetime
from pathlib import Path
from typing import Annotated, TypedDict

import pandas as pd
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy, Send

HARDER = Path(__file__).resolve().parents[3] / "data" / "evals" / "harder"
WRONGFUL_DECLINE = 1500
NEEDLESS_REFERRAL = 50


def load_labels() -> dict[str, dict]:
    """The handlers' decisions on the harder claims, by claim id."""
    decisions = json.loads((HARDER / "decisions.json").read_text(encoding="utf-8"))
    return {decision["claim_id"]: decision for decision in decisions}


# Day 1's measures, as in the lab


def is_right(answer: dict, expected: dict) -> bool:
    """True when the decision matches the handler's and the payout is within a dollar."""
    return answer["decision"] == expected["decision"] and abs(answer["payout"] - expected["payout"]) <= 1


def mistake_cost(answer: dict, expected: dict) -> float:
    """What the agent's answer costs UnderCover, against the handler's decision."""
    if answer["decision"] == expected["decision"]:
        return abs(answer["payout"] - expected["payout"]) if answer["decision"] == "approve" else 0
    if answer["decision"] == "decline":
        return WRONGFUL_DECLINE
    if answer["decision"] == "approve":
        return answer["payout"]
    return NEEDLESS_REFERRAL


def run_scores(results: list[dict], labels: dict[str, dict]) -> dict[str, float]:
    """The scores for a whole run, quality and time, as plain floats so a checkpointer can save them."""
    table = pd.DataFrame(
        [
            {
                "right": is_right(answer, labels[answer["claim_id"]]),
                "same_decision": answer["decision"] == labels[answer["claim_id"]]["decision"],
                "mistake_cost": mistake_cost(answer, labels[answer["claim_id"]]),
                "referred": answer["decision"] == "refer",
                "started": answer["started"],
                "finished": answer["finished"],
                "seconds": (answer["finished"] - answer["started"]).total_seconds(),
            }
            for answer in results
        ]
    )
    return {
        "claims": float(len(table)),
        "decision_accuracy": float(table["same_decision"].mean()),
        "accuracy": float(table["right"].mean()),
        "cost_of_mistakes": float(table["mistake_cost"].sum()),
        "straight_through": float((~table["referred"]).mean()),
        "seconds": (table["finished"].max() - table["started"].min()).total_seconds(),
        "slowest_claim": float(table["seconds"].max()),
        "seconds_per_claim": float(table["seconds"].mean()),
    }


# The dispatcher


class Dispatch(TypedDict, total=False):
    """What the dispatcher keeps for one run, now with the run's scores."""

    claims: list[str]
    results: Annotated[list, operator.add]
    scores: dict[str, float]


Worker = Callable[[str], dict]


def build_dispatcher(
    worker: Worker,
    claim_ids: Iterable[str],
    labels: dict[str, dict],
    checkpointer=None,
    retry_policy: RetryPolicy | None = None,
    on_score: Callable[[dict], None] | None = None,
):
    """Compile list_claims -> work_claim (one per claim) -> score_run -> END.

    on_score is called with the scores each time score_run runs, so a test can count the runs."""
    claim_ids = list(claim_ids)

    def list_claims(state: Dispatch) -> dict:
        return {"claims": claim_ids}

    def fan_out(state: Dispatch) -> list[Send]:
        return [Send("work_claim", claim_id) for claim_id in state["claims"]]

    def score_run(state: Dispatch) -> dict:
        scores = run_scores(state["results"], labels)
        if on_score:
            on_score(scores)
        return {"scores": scores}

    builder = StateGraph(Dispatch)
    builder.add_node("list_claims", list_claims)
    builder.add_node("work_claim", worker, retry_policy=retry_policy or RetryPolicy(max_attempts=3))
    builder.add_node("score_run", score_run)
    builder.add_edge(START, "list_claims")
    builder.add_conditional_edges("list_claims", fan_out, ["work_claim"])
    builder.add_edge("work_claim", "score_run")
    builder.add_edge("score_run", END)
    return builder.compile(checkpointer=checkpointer)


def make_stand_in(labels: dict[str, dict], wrong: Iterable[str] = (), delay: float = 1.0) -> Worker:
    """A stand-in claim agent: it answers as the handler did, except on the claims in wrong,
    where it refers the claim. It takes delay seconds, like the lab's stand-in."""
    wrong = set(wrong)

    def stand_in(claim_id: str) -> dict:
        started = datetime.now()
        time.sleep(delay)
        expected = labels[claim_id]
        if claim_id in wrong:
            answer = {"decision": "refer", "payout": 0.0, "rationale": "Stand-in referral"}
        else:
            answer = {"decision": expected["decision"], "payout": float(expected["payout"]), "rationale": "Stand-in"}
        return {"results": [{"claim_id": claim_id, **answer, "started": started, "finished": datetime.now()}]}

    return stand_in


def send_scores(langfuse, trace_id: str, scores: dict[str, float]) -> None:
    """Add a run's scores to its trace in Langfuse, as the lab does."""
    for name, value in scores.items():
        langfuse.create_score(trace_id=trace_id, name=name, value=float(value))


def main() -> None:
    labels = load_labels()
    claim_ids = sorted(labels)
    wrong = claim_ids[:3]
    dispatcher = build_dispatcher(make_stand_in(labels, wrong=wrong, delay=1.0), claim_ids, labels)
    for cap in (1, 5, 25):
        state = dispatcher.invoke({}, {"max_concurrency": cap})
        scores = {name: round(value, 3) for name, value in state["scores"].items()}
        print(f"{cap} at once: {scores}")


if __name__ == "__main__":
    main()
