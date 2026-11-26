"""Find the claims several runs got wrong, and judge whether they share a reason."""

from collections import Counter
from dataclasses import dataclass, fields, replace
from typing import Any, Literal, cast

import pandas as pd
from IPython.display import Markdown, display
from openai import OpenAI
from pydantic import BaseModel, Field

Result = dict[str, Any]

JUDGE = "anthropic/claude-sonnet-5.5"
REPEATED = 2

JUDGE_PROMPT = """You are reviewing answers that AI models gave on a travel
insurance claim. Every answer reached the same decision and payout, and the claims
handler disagreed with all of them.

Sort the answers into groups. Two answers belong in the same group only when they rely
on the same policy section and the same deciding fact. Differences in wording don't
matter. Put every answer in exactly one group. An answer that shares its reason with no
other answer gets a group of its own.

For each group, say how its reason departs from the handler's:
- missing_information: the handler relied on something the answers did not have, such as
  a claims manual or the customer's history
- different_reading: the answers read the policy wording or the facts of the claim
  differently from the handler
- arithmetic: the answers agree with the handler on what is covered but work out the
  payout differently
- other: none of these
"""


@dataclass
class _Consensus:
    claim_id: str
    times_missed: int
    consensus: str = "no agreement"
    agreed: int = 0
    gap: str = ""
    cost: float = 0.0
    section: str = ""
    summary: str = ""
    gap_explanation: str = ""
    example: str = ""
    example_run: str = ""


class ReasonGroup(BaseModel):
    """Answers that reached their decision for the same reason."""

    answers: list[int] = Field(description="The numbers of the answers in this group")
    section: str = Field(description="The policy section these answers rely on")
    summary: str = Field(
        description="One sentence giving the reason these answers share"
    )
    gap_explanation: str = Field(
        description="One sentence on where this reason and the handler's part ways"
    )
    gap: Literal["missing_information", "different_reading", "arithmetic", "other"]


class Judgment(BaseModel):
    """The answers on one claim, sorted into groups by their reason."""

    groups: list[ReasonGroup]


def _run_label(result: Result) -> str:
    model, effort, technique = result["model"], result["effort"], result["technique"]
    return f"{model} at {effort} ({technique})"


def _outcome(answer: Result) -> tuple[str, int]:
    return answer["decision"], round(answer["payout"])


def pool_misses(experiments: list[list[Result]]) -> pd.DataFrame:
    """Pool the results of every run into one DataFrame and keep the wrong answers."""
    rows = [
        {**result, "run": _run_label(result)}
        for results in experiments
        for result in results
    ]
    pooled = pd.DataFrame(rows)
    return pooled.loc[~pooled["right"]]


def misses_by_run(misses: pd.DataFrame) -> pd.DataFrame:
    """Each claim, the number of runs that missed it and which runs they were."""
    runs = misses.groupby("claim_id")["run"]
    table = pd.DataFrame(
        {"times_missed": runs.count(), "missed_by": runs.agg(", ".join)}
    )
    return table.sort_values("times_missed", ascending=False)


def _judge(
    client: OpenAI, claim: Result, label: Result, answers: list[Result], model: str
) -> tuple[Judgment, float]:
    numbered = "\n\n".join(
        f"Answer {number}: {answer['rationale']}"
        for number, answer in enumerate(answers, 1)
    )
    summary = claim["summary"]
    story = claim["story"]
    # Every answer here shares one decision and payout
    decision = answers[0]["decision"]
    payout = answers[0]["payout"]
    handler_decision = label["decision"]
    handler_payout = label["payout"]
    handler_reason = label["reason"]
    user_prompt = f"""# Claim

{summary}

{story}

# The answers' decision

{decision} ${payout:,.2f}

# The handler's decision

{handler_decision} ${handler_payout:,.2f}. {handler_reason}

# Answers

{numbered}
"""
    response = client.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": JUDGE_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format=Judgment,
        extra_body={"provider": {"require_parameters": True}},
    )
    cost: float = getattr(response.usage, "cost", 0.0)
    return cast(Judgment, response.choices[0].message.parsed), cost


def _consensus_on_claim(
    client: OpenAI, answers: list[Result], claim: Result, label: Result, model: str
) -> _Consensus:
    row = _Consensus(claim["claim_id"], len(answers))

    counts = Counter(_outcome(answer) for answer in answers)
    top_outcome, count = counts.most_common(1)[0]
    if count * 2 <= len(answers):
        return row
    largest = [answer for answer in answers if _outcome(answer) == top_outcome]

    judgment, cost = _judge(client, claim, label, largest, model)
    row.cost = cost
    grouped = []
    for group in judgment.groups:
        grouped += group.answers
    if sorted(grouped) != list(range(1, len(largest) + 1)):
        return replace(row, consensus="judge error")

    biggest_group = max(judgment.groups, key=lambda group: len(group.answers))
    if len(biggest_group.answers) * 2 <= len(answers):
        return row
    example = largest[biggest_group.answers[0] - 1]
    return replace(
        row,
        consensus=f"{example['decision']} ${example['payout']:,.2f}",
        agreed=len(biggest_group.answers),
        gap=biggest_group.gap,
        section=biggest_group.section,
        summary=biggest_group.summary,
        gap_explanation=biggest_group.gap_explanation,
        example=example["rationale"],
        example_run=example["run"],
    )


def find_consensus(
    client: OpenAI,
    misses: pd.DataFrame,
    claims: list[Result],
    labels: dict[str, Result],
    model: str = JUDGE,
) -> pd.DataFrame:
    """Judge every claim missed by two or more runs, with an OpenRouter client."""
    claims_by_id = {claim["claim_id"]: claim for claim in claims}
    rows = []
    for claim_id, group in misses.groupby("claim_id"):
        if len(group) < REPEATED:
            continue
        answers = cast(list[Result], group.to_dict("records"))
        claim, label = claims_by_id[str(claim_id)], labels[str(claim_id)]
        rows.append(_consensus_on_claim(client, answers, claim, label, model))
    return pd.DataFrame(rows, columns=[field.name for field in fields(_Consensus)])


def show_consensus(consensus: pd.DataFrame, labels: dict[str, Result]) -> None:
    """Show the detail for each claim where the misses agree."""
    for row in consensus.to_dict("records"):
        if row["agreed"]:
            label = labels[row["claim_id"]]
            handler = f"{label['decision']} ${label['payout']:,.2f}"
            display(
                Markdown(
                    f"**{row['claim_id']}, {label['difficulty']}**: "
                    f"{row['agreed']} of {row['times_missed']} misses agree on "
                    f"{row['consensus']}, where the handler said {handler}\n\n"
                    f"- Shared reason ({row['section']}): {row['summary']}\n"
                    f"- Gap, {row['gap']}: {row['gap_explanation']}\n"
                    f"- Handler: {label['reason']}\n"
                    f"- Example, from {row['example_run']}: {row['example']}\n"
                )
            )
