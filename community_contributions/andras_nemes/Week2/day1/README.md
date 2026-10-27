# Week 2 Day 1: concise wording and business cost

Andras Nemes. Assignment from `labs/week2day1.ipynb`, using `data/policy_wording_short.md` from Week 1 Day 4.

The submission includes experiment code and a CSV with nine run summaries. It uses the original lab's payout function in `labs/week2day1_payout.py`.

## Run

From the repository root, after the course's `uv sync`:

```powershell
uv run community_contributions/andras_nemes/Week2/day1/week2day1_assignment.py
```

This displays the saved comparisons and penalty scenarios without credentials or network calls.

To repeat the three concise-wording runs, first complete Part 4 of the original lab so your Langfuse project has the `harder-claims` dataset. Use the OpenRouter and Langfuse keys already configured in the root `.env`, then run:

```powershell
uv run community_contributions/andras_nemes/Week2/day1/week2day1_assignment.py --run
```

`--run` makes paid model calls for three runs of 25 claims. Completed runs are cached under the git-ignored `results/` directory, so rerunning resumes from those files. The comparison combines the saved baseline and full-wording runs with your new concise runs. Rename `results/` to start fresh.

Langfuse can take a short while to finish processing traces. If the script stops with "Trace data is not complete yet", wait a minute and run the same command again. The model calls for finished runs are not repeated.

## What changed

- Replaced full wording with the complete concise wording; changed the instruction's `section 10` reference to `Payment`.
- Kept Luna at reasoning `none`, both tools, full claim documents, policy JSON, the same 25 claims and sequential execution.
- Summed API cost and input tokens across every model message. Measured agent duration from LangGraph spans using Langfuse's v4 observation read API.
- Recomputed business costs from fixed predictions and wrongful-decline counts, allowing penalty comparisons without model reruns.

## Results

Recorded October 23 and 24, 2026: three repetitions of the same 25 claims per experiment. The concise-wording runs were repeated on October 24 and replaced an earlier set (see below). Accuracy requires a matching decision and payout within $1. Costs are mean totals per 25-claim run; time is mean seconds per claim.

| Experiment | Correct / 75 | Accuracy | Mistake cost at $1,500 penalty | API cost | Seconds |
|---|---:|---:|---:|---:|---:|
| Full wording, no payout tool | 37 | 49.33% | $4,293.59 | $0.005647 | 5.08 |
| Full wording + payout tool | 62 | 82.67% | $967.81 | $0.010132 | 10.52 |
| Concise wording + payout tool | 65 | 86.67% | $958.28 | $0.010674 | 7.51 |

Concise wording scored three more correct results out of 75 and ran about 29% faster per claim, but cost about 5% more in API spend even though it used about 18% fewer input tokens. I did not investigate why the API cost rose. Three repetitions of 25 claims do not establish a real accuracy difference. Concise runs scored 23, 21 and 21 out of 25, and full-wording runs scored 21, 18 and 23, so the spread within each experiment is as large as the gap between them. Routing, caching and load also affect timing and cost.

Both wordings produced exactly one wrongful decline in 75 results. The concise agent declined CLM-1209, a claim that should be approved for $4,180.15, in one run, and referred it in another. The rest of the concise mistakes were payout errors on correctly approved claims: CLM-1217 overpaid $250 in two runs, CLM-1216 overpaid $328 in two runs, and CLM-1207 was off by $32.50 to $53.85 in all three. The CLM-1216 overpayment matches the earlier concise runs and is consistent with the camera and lens being split instead of treated as a set, an example the short wording omits. On CLM-1203, concise wording was correct in all three runs, compared with one full-wording run.

| Wrongful-decline penalty | Full wording + tool | Concise wording + tool | Lower business cost |
|---|---:|---:|---|
| $0 | $467.81 | $458.28 | Concise |
| $500 | $634.48 | $624.95 | Concise |
| $1,500 | $967.81 | $958.28 | Concise |
| $5,000 | $2,134.48 | $2,124.95 | Concise |
| $10,000 | $3,801.14 | $3,791.62 | Concise |

Because both wordings have one wrongful decline, the penalty cancels out and there is no break-even point. Concise wording is cheaper at every penalty, by $9.53 per 25-claim run. That gap is tiny next to the run-to-run spread in mistake cost, which ranges from $82 to $802 per run for full wording and from $283 to $611 for concise wording before the penalty.

I would lean towards concise wording: it is no worse on accuracy or business cost, and it is noticeably faster. I would not call the choice settled. It rests on a single wrongful decline for each wording, and the two payout errors that repeat (CLM-1216 and CLM-1217) point at a gap in the short wording that is worth fixing before relying on it.

### Earlier concise measurement

An earlier set of three concise runs scored 63 out of 75 (84.00%), with a mean mistake cost of $1,894.13 at the $1,500 penalty, $0.009707 in API cost and 10.57 seconds per claim. That set had three wrongful approvals and no wrongful declines, which made full wording the cheaper choice below a $4,278.97 penalty. The repeat above replaced it in `comparison_runs.csv` and reversed that ranking. The two sets use the same model, wording, tools and claims, so the gap between them is itself a measure of how much three runs of 25 claims can vary.
