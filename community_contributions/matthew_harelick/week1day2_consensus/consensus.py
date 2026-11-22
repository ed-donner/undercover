"""Compare the claims that several runs got wrong, and ask whether their answers agree.

A run is a list of results, one per claim. Each result is a dict with model, effort, technique,
claim_id, decision, payout, rationale and right, as the labs' run functions produce.
A result can carry its own "run" label; otherwise one is made from model, effort and technique.

Agreement here is consensus, not truth. The handler's decision is the truth, and every answer
compared is one the handler disagreed with.
"""

from typing import Literal

import pandas as pd
from IPython.display import Markdown, display
from pydantic import BaseModel, Field

JUDGE = "anthropic/claude-sonnet-5.5"
REPEATED = 2

JUDGE_PROMPT = """You are reviewing answers that AI models gave on a travel insurance claim.
Every answer reached the same decision and payout, and the claims handler disagreed with all of them.

Sort the answers into groups. Two answers belong in the same group only when they rely on the same policy section and the same deciding fact. Differences in wording don't matter.
Put every answer in exactly one group. An answer that shares its reason with no other answer gets a group of its own.

For each group, say how its reason departs from the handler's:
- missing_information: the handler relied on something the answers did not have, such as a claims manual or the customer's history
- different_reading: the answers read the policy wording or the facts of the claim differently from the handler
- arithmetic: the answers agree with the handler on what is covered but work out the payout differently
- other: none of these
"""

CONSENSUS_COLUMNS = [
    "claim_id",
    "times_missed",
    "consensus",
    "agreed",
    "gap",
    "cost",
    "section",
    "summary",
    "gap_explanation",
    "example",
    "example_run",
]


class ReasonGroup(BaseModel):
    """Answers that reached their decision for the same reason."""

    answers: list[int] = Field(description="The numbers of the answers in this group")
    section: str = Field(description="The policy section these answers rely on")
    summary: str = Field(description="One sentence giving the reason these answers share")
    gap_explanation: str = Field(description="One sentence on where this reason and the handler's part ways")
    gap: Literal["missing_information", "different_reading", "arithmetic", "other"]


class Judgment(BaseModel):
    """The answers on one claim, sorted into groups by their reason."""

    groups: list[ReasonGroup]


def run_label(result):
    """The name of the run a result came from."""
    return result.get("run") or f"{result['model']} at {result['effort']} ({result['technique']})"


def pool_misses(experiments):
    """Pool the results of every run into one DataFrame and keep the answers that were wrong."""
    rows = [{**result, "run": run_label(result)} for results in experiments for result in results]
    pooled = pd.DataFrame(rows)
    return pooled[~pooled["right"].astype(bool)]


def count_misses(misses):
    """Each claim and the number of runs that missed it."""
    return misses.groupby("claim_id").size().rename("times_missed").sort_values(ascending=False).to_frame()


def misses_by_run(misses):
    """Each claim, the number of runs that missed it and which runs they were."""
    table = misses.groupby("claim_id")["run"].agg(times_missed="count", missed_by=", ".join)
    return table.sort_values("times_missed", ascending=False)


def judge(client, claim, label, answers, model=JUDGE):
    """Ask the judge to sort the answers on one claim by their reason."""
    numbered = "\n\n".join(f"Answer {number}: {answer['rationale']}" for number, answer in enumerate(answers, 1))
    user_prompt = f"""# Claim

{claim["summary"]}

{claim["story"]}

# The answers' decision

{answers[0]["decision"]} ${answers[0]["payout"]:,.2f}

# The handler's decision

{label["decision"]} ${label["payout"]:,.2f}. {label["reason"]}

# Answers

{numbered}
"""
    response = client.chat.completions.parse(
        model=model,
        messages=[{"role": "system", "content": JUDGE_PROMPT}, {"role": "user", "content": user_prompt}],
        response_format=Judgment,
        extra_body={"provider": {"require_parameters": True}},
    )
    return response.choices[0].message.parsed, response.usage.cost


def consensus_on_claim(client, answers, claim, label, model=JUDGE):
    """Look for a reason shared by more than half of the answers that missed one claim."""
    row = {
        "claim_id": claim["claim_id"],
        "times_missed": len(answers),
        "consensus": "no agreement",
        "agreed": 0,
        "gap": "",
        "cost": 0.0,
    }

    # The decision and payout come first, and need no model
    outcomes = {}
    for answer in answers:
        outcomes.setdefault((answer["decision"], round(answer["payout"])), []).append(answer)
    largest = max(outcomes.values(), key=len)
    if len(largest) * 2 <= len(answers):
        return row

    judgment, cost = judge(client, claim, label, largest, model)
    row["cost"] = cost
    numbers = sorted(number for group in judgment.groups for number in group.answers)
    if numbers != list(range(1, len(largest) + 1)):
        return {**row, "consensus": "judge error"}

    top = max(judgment.groups, key=lambda group: len(group.answers))
    if len(top.answers) * 2 <= len(answers):
        return row
    example = largest[top.answers[0] - 1]
    return {
        **row,
        "consensus": f"{example['decision']} ${example['payout']:,.2f}",
        "agreed": len(top.answers),
        "gap": top.gap,
        "section": top.section,
        "summary": top.summary,
        "gap_explanation": top.gap_explanation,
        "example": example["rationale"],
        "example_run": example["run"],
    }


def find_consensus(client, misses, claims, labels, model=JUDGE):
    """Judge every claim missed by two or more runs. client is an OpenAI client pointed at OpenRouter."""
    claims_by_id = {claim["claim_id"]: claim for claim in claims}
    times_missed = misses.groupby("claim_id").size()
    rows = []
    for claim_id in times_missed[times_missed >= REPEATED].index:
        answers = misses[misses["claim_id"] == claim_id].to_dict("records")
        rows.append(consensus_on_claim(client, answers, claims_by_id[claim_id], labels[claim_id], model))
    return pd.DataFrame(rows, columns=CONSENSUS_COLUMNS)


def show_consensus(consensus, labels):
    """Show the detail for each claim where the misses agree."""
    for row in consensus.to_dict("records"):
        if row["agreed"]:
            label = labels[row["claim_id"]]
            display(
                Markdown(f"""**{row["claim_id"]}, {label["difficulty"]}**: {row["agreed"]} of {row["times_missed"]} misses agree on {row["consensus"]}, where the handler said {label["decision"]} ${label["payout"]:,.2f}

- Shared reason ({row["section"]}): {row["summary"]}
- Gap, {row["gap"]}: {row["gap_explanation"]}
- Handler: {label["reason"]}
- Example, from {row["example_run"]}: {row["example"]}
""")
            )
