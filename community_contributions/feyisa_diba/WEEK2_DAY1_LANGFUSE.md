# Week 2 Day 1: full against short policy wording, in Langfuse

Feyisa Diba. The notebook is [week2day1_langfuse.ipynb](week2day1_langfuse.ipynb), and every answer from every run is in [week2day1_langfuse_results.csv](week2day1_langfuse_results.csv).

The assignment runs a third experiment, with the concise wording from Week 1 Day 4 and the payout tool, and asks three questions. Other students' answers disagree, often because one run of 25 claims is noisy, so I tried to separate the difference from the noise.

## The answers

1. **Does the short wording keep the accuracy? No.** Accuracy falls from 93.3% to 81.3%, a drop of 12 points with a 95% interval of 1 to 24 points. The best short run only matched the worst full run. Three sentences the short wording leaves out cause most of the drop.
2. **Is it cheaper or faster? Slightly, by amounts that don't matter.** It costs 8.7% less, about $0.0009 for a run of 25 claims. It's probably a little faster, about 1.7 seconds a claim, but most of that gap comes from one run.
3. **Does changing `WRONGFUL_DECLINE` change the choice? No.** The full wording made fewer wrongful declines and fewer other mistakes, so it costs less at every figure from $0 to $10,000, and in a scenario where the cost grows with the claim. But three runs don't settle the gap in cost of mistakes: the full wording comes out cheaper in about 70% of bootstrap resamples.

I would keep the full wording.

## What I did

**The setup.** These are Ed's agents, tools, model (GPT-6 Luna through OpenRouter, reasoning off) and cost matrix, run on the 25 harder claims in the Langfuse dataset `harder-claims`. There are three experiments:

- **Baseline:** the full wording, without the payout tool.
- **Payout tool:** the full wording, with the payout tool.
- **Short wording + payout tool:** the assignment.

The short wording has no numbered sections, so its agent's instructions say "the Payment section" where Ed's say "section 10", as Andras Nemes did. Nothing else changes.

**Three runs of each, taking turns.** The runs went in rounds: one run of each experiment, then the second of each, then the third. The provider's speed changed during the session. Some calls took 36 seconds where most took 1 or 2, and one failed with "Our servers are currently overloaded". Taking turns stops the time of day from looking like a difference between the wordings.

**Every claim counts.** Langfuse's `run_experiment` leaves out any claim whose task raises an error, and runs the run evaluators on the rest. Langfuse still lists the run with all 25 items.

In my first run of the lab, two claims hit OpenRouter's limit of 20 requests a minute for new accounts. The baseline's accuracy of 0.435 was really 10 claims right out of 23. Here the task waits to stay under the limit and retries a claim that fails. A claim that still fails counts as a referral, as the lab counts a claim the agent didn't decide.

In these nine runs no claim failed. One, CLM-1201 in baseline run 1, got a 502 from the provider and succeeded on the retry. The lab's code would have dropped it.

**More measures.** For each claim the notebook also records:

- the time, which is the wall-clock time of the whole agent loop, not counting any waits for the rate limit
- the input tokens
- the tokens read from the provider's cache
- the model cost OpenRouter reports

**Is a difference real?** Both wordings decided the same claims, so I compared them claim by claim. For each claim I took its average over the three runs with each wording, then resampled the 25 claims 10,000 times to get a 95% interval for each difference. When the interval includes zero, these runs can't tell the two apart.

**`WRONGFUL_DECLINE`.** Nothing in the repo says what a wrongful decline really costs UnderCover. The course uses $1,500 throughout Week 2, including in the Week 2 Day 4 scoreboard, so I kept it as the agreed figure. Then I scored the same answers again, with no new model calls:

- I worked out the break-even figure where the choice of wording would flip. This uses Arthur JZL's observation that the cost of mistakes is a straight line in `WRONGFUL_DECLINE`.
- I scored five flat figures: $0, $500, $1,500, $5,000 and $10,000.
- I scored a claim-size scenario: $500 for the complaint and the appeal, plus half of what the handler would have paid. This and the flat figures are assumptions to test, not UnderCover's figures.

Each scenario's cost is added to every run in Langfuse as another score: `cost_of_mistakes_wd_0`, `cost_of_mistakes_wd_500`, `cost_of_mistakes_wd_5000`, `cost_of_mistakes_wd_10000` and `cost_of_mistakes_claim_size`. They show beside the original scores in Langfuse's comparison view.

## Results

### The averages of three runs

The figures in brackets are the lowest and highest run.

| | Baseline | Payout tool | Short wording + payout tool |
|---|---|---|---|
| Accuracy | 46.7% (44 to 48) | **93.3%** (84 to 100) | 81.3% (80 to 84) |
| Decision accuracy | 76.0% | **97.3%** | 94.7% |
| Kappa | 0.643 | **0.956** | 0.911 |
| Cost of mistakes a run, at $1,500 | $10,035 | **$1,691** | $2,535 |
| Wrongful declines a run | 3.33 | **0.67** | 1.00 |
| Straight-through rate | 65% | 76% | 76% |
| Model cost a run | $0.0074 | $0.0098 | $0.0090 |
| Seconds a claim (median) | see below | 7.7 (7.2) | 5.9 (6.3) |
| Input tokens a claim | 6,452 | 9,831 | 7,806 |
| Input read from cache | 84% | 89% | 87% |
| Failed claims | 0 | 0 | 0 |

The handlers refer 6 of the 25 claims, so their straight-through rate is 76%, the same as both payout-tool agents.

### Full against short, claim by claim

| | Full | Short | Difference | 95% interval | Clear? |
|---|---|---|---|---|---|
| Accuracy | 93.3% | 81.3% | -12.0 points | -24.0 to -1.3 | yes |
| Cost of mistakes a run | $1,691 | $2,535 | +$843 | -$1,630 to +$3,695 | no |
| Model cost a run | $0.0098 | $0.0090 | -$0.0009 | -$0.0017 to $0.0000 | only just |
| Seconds a claim | 7.68 | 5.94 | -1.74 | -2.40 to -1.13 | see below |
| Input tokens a claim | 9,831 | 7,806 | -2,025 | -2,475 to -1,629 | yes |

For comparison, the payout tool against the baseline is clear on every measure: accuracy rises 46.7 points, with an interval of 29 to 64.

### Where the short wording goes wrong

Three claims cause 73% of the short wording's cost of mistakes. I checked each one against the agent's rationale, and for CLM-1216 against the payout-tool call in the Langfuse trace.

| Claim | Short wording | Full wording | Cause |
|---|---|---|---|
| CLM-1209, an injury rafting at grade 3; the handler approved $4,180.15 | Declined in 3 of 3 runs | Right in 2 of 3 | The full wording defines "Adventure sports are ... white-water rafting above grade 3", so grade 3 isn't excluded. The short one says "Adventure Sports **covers** ... white-water rafting above grade 3", and all three rationales read it as "rafting is covered only above grade 3" and declined. |
| CLM-1216, a camera and its lens with other items; the handler approved $1,677.90 | Overpaid $328 in 3 of 3 runs | Right in 3 of 3 | The full wording says "A pair or a set, such as a pair of shoes, a suit or a camera with its lens, counts as one item". The short wording keeps the rule and drops the example. The traces show the agent sent the $1,049 camera body and the $479 lens to the payout tool as two items, each under the $1,200 limit, where the full-wording agent sent one $1,528 set, limited to $1,200. |
| CLM-1207, a sketchbook claimed at $950 for the drawings in it; the handler approved $1,306.72 | Underpaid $32.50 in 2 of 3 runs | Right in 3 of 3 | The full wording says "For a laptop, a drive, a notebook or a document we pay for the physical item, and we do not pay for the data, the writing or the work it holds." The short wording only excludes "the value of data or work on a device", and the agent left the sketchbook out altogether. |

The same three claims show up in other students' runs:

- **CLM-1216, overpaid $328:** James Horrigan, Arthur JZL, Andras Nemes and Darko Martinovic. Andras traced it to the camera and lens.
- **CLM-1207, the sketchbook:** James Horrigan.
- **The rafting rule:** Alla Mosina.

The other mistakes look like slips that either wording can make. Once, the short wording approved CLM-1219 for $1,500, saying the theft was reported within 24 hours when it was reported 31 hours later; the 24-hour rule is in both wordings.

The full wording's two wrongful declines are odd in a different way. In both, the rationale argues against declining:

- **CLM-1209, run 1:** it says the activity "is not within the defined adventure-sports exclusion".
- **CLM-1218, run 3:** it says the claim "requires review".

A check that flags a decision its own rationale argues against would have caught both. I didn't build one.

### Cost and speed

- **Tokens.** The short wording has 41% fewer words, but each claim sends only 21% fewer input tokens. The policy record, the claim and the tool calls go with every model call too.
- **Cost.** The cost falls by less again, 8.7%, because most of the input is read from the provider's cache at a lower price. Caching also changed over the session. The share read from cache rose from 71% to 80% in each experiment's first run to about 95% in its third, and the model cost of a run fell by about a third with it: the full wording's runs cost $0.0123, $0.0089 and $0.0083. The order of the runs moved the cost more than the wording did. That backs up Alla Mosina's explanation with data.
- **Speed.** The short wording averaged 5.9 seconds a claim against 7.7, and its median was 6.3 against 7.2. Most of the gap is in the first pair of runs, when the provider was slower: run by run it was 6.1 against 10.2, then 5.6 against 6.8, then 6.1 against 6.1. The bootstrap interval treats each claim as independent, so it can't see a slow period that affects a whole run. I read it as "probably a little faster".
- **Baseline time isn't comparable.** Baseline runs 1 and 2 ran at the same time, from two notebook kernels, while the provider was overloaded, at 21 to 24 seconds a claim. Run 3 took 4.3 seconds a claim. Their accuracy is unaffected.

### The cost of a wrongful decline

Each experiment's cost of mistakes is its other mistakes plus its wrongful declines times `WRONGFUL_DECLINE`:

- **Payout tool, full wording:** $691 of other mistakes, plus 0.67 wrongful declines a run
- **Short wording:** $1,035 of other mistakes, plus 1.00 wrongful declines a run

The full wording is lower on both, so the lines never cross and there is no break-even.

| `WRONGFUL_DECLINE` | Baseline | Full | Short | Cheaper | Full cheaper in resamples |
|---|---|---|---|---|---|
| $0 | $5,035 | $691 | $1,035 | full | 67% |
| $500 | $6,701 | $1,025 | $1,535 | full | 72% |
| **$1,500, agreed** | $10,035 | $1,691 | $2,535 | full | 72% |
| $5,000 | $21,701 | $4,025 | $6,035 | full | 68% |
| $10,000 | $38,368 | $7,358 | $11,035 | full | 67% |
| $500 + half the payout | $11,913 | $2,459 | $3,625 | full | 69% |

The figure never changes the choice. But the last column shows the gap in cost of mistakes isn't settled. It rests on a few large events: the short wording's three declines of CLM-1209, its one $1,500 payment on CLM-1219, and the full wording's one underpayment of $1,786 on CLM-1203. Accuracy is the clearer evidence of the two.

## Conclusions

1. **Keep the full wording.** The short wording loses 12 points of accuracy to save less than a tenth of a cent a run.
2. **The short wording's losses are specific: three sentences.** The next experiment I'd run is the short wording with those three sentences restored from the full wording. I haven't run it.
3. **`WRONGFUL_DECLINE` doesn't change the choice here.** What matters more is that the gap in cost of mistakes needs more runs or more claims to settle. Accuracy settles sooner, because the cost of mistakes is dominated by a few large mistakes.
4. **Check that every run scored all its claims.** A run that dropped claims still shows all of them in Langfuse. A task that never raises, plus a column of failed claims, makes the gap visible.

## Limits

- 25 claims and three runs, on one model at one reasoning setting.
- The interval for time per claim is too narrow, as explained above.
- The scenario figures are assumptions, not UnderCover's.
- The model costs are what OpenRouter reported, and the caching is the provider's own.

## Running it

The notebook runs from this folder on the `.venv` kernel, with `OPENROUTER_API_KEY` and the Langfuse keys in `.env`, as in the lab. Each finished run is saved to the CSV and loaded from there instead of being run again, so the analysis can be run again for free. Delete the CSV to start afresh. The nine runs cost $0.079 in model calls. A run takes about 5 minutes, about 2 of them waiting for the rate limit.

Langfuse Cloud switched off its v3 API for dataset runs on 19 November 2026, so the notebook reads runs back with the v4 experiments API. New scores can take a few minutes to appear there.

## Credits

Ideas from other students' Week 2 Day 1 contributions:

- **Arthur JZL:** the cost of mistakes as a straight line, and the break-even figure
- **Darko Martinovic:** reading runs back from Langfuse's v4 experiments API
- **Andras Nemes:** "the Payment section" in place of "section 10", and the camera and lens
- **Alla Mosina:** the rafting rule, and caching as the reason the cost hardly moves
- **James Horrigan:** the sketchbook
- **Rongjun Geng and VerBodh:** scoring saved answers again at several figures
