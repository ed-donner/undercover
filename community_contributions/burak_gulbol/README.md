# Week 1 Day 2: the cheapest consistent agent, and what its mistakes cost

Burak Gülbol

**Challenge:** with a goal of at least 15 / 25 correct consistently, using the agent, what is the cheapest model you can find?

**Answer:** the lab's own `openai/gpt-6-luna` at `low`: 17, 16 and 18 on three runs of the queue (worst 16), about **$0.0074 a run**, and **20 / 25** on the held-out set.

**The bigger finding:** the model bill is under a cent a run, but the mistakes are worth hundreds of dollars. Comparing models only on accuracy and token cost hides that.

## Results

All runs use the lab's agent unchanged (same prompt, tools and scoring). Each model ran three times on the 25-claim queue; cost is what OpenRouter billed.

| Model (lab's agent) | Right, 3 runs | Worst | Cost / run | Paid without review / run | Overpaid / run | Underpaid / run |
|---|---|---|---|---|---|---|
| **gpt-6-luna (low)** | 17, 16, 18 | **16** | **$0.0074** | $814 | $288 | $112 |
| ling-3.0-flash | 15, 16, 14 | 14 | $0.0092 | $1,229 | $239 | $60 |
| gpt-6-luna (low), held-out, 1 run | 20 | 20 | $0.0092 | $420 | $0 | $30 |

"Paid without review" is the payout on claims the handler would have referred but the agent approved. It is exposure, not loss, and with only a few claims behind each figure, the dollar amounts show direction rather than precision.

## What I learned

1. **Judge on the worst of several runs.** Accuracy and cost both vary from run to run (Luna's cost ranged from $0.0064 to $0.0089 on the same queue). Ling looked fine on two runs and missed the goal on the third.
2. **One claim is not a cost estimate.** Ling looked about 20% cheaper than Luna on a single claim and was about 25% more expensive over the queue.
3. **The score hides the kind of mistake.** Luna and Ling are two points apart on average, but Ling approved about $415 a run more of claims that needed review. For an insurer, a wrong approval costs far more than a needless referral.
4. **Most remaining errors are systematic, not random.** The same claims fail on every run:
   - The three `manual` claims are approved every time because the agent can't see the customer's claim history or the claims manual. A bigger model can't fix missing information; a tool can.
   - CLM-1004 and CLM-1021 get the right decision and the same wrong payout every time. Arithmetic belongs in code.
5. **The result reproduces.** ArthurJZL and fazal_abbas found the same winner at a similar cost, and the other contributions in this folder had already ruled out most cheaper models, which is why I only tested Ling further.

## Next steps I'd try

- A `get_claim_history` tool and a claims-manual lookup for the `manual` claims (as in okafor_pascal_week1day2).
- Work out the payout in code and let the model only classify the items.
- Put the policy record in the prompt and stop after `record_decision`, dropping the two model calls that need no judgment.
- Then re-check the cheaper models, since a better agent may change which model is cheapest.

## Running the notebook

[`week1day2_cheapest_agent.ipynb`](week1day2_cheapest_agent.ipynb) keeps the outputs of the runs above. Running it from top to bottom repeats all seven runs: about an hour (the loops pause to stay under OpenRouter's new-account limit of 20 requests a minute per model) and a few cents, and the numbers will differ a little from run to run.
