# Week 1 Day 2: a lean agent for UnderCover

Varun Singh

**The main takeaway: change the agent before you change the model.** The model stayed the same throughout. The whole gain came from four changes to how the agent works: fixed steps move from tools into code, code does the arithmetic, the agent gets the information it was missing, and it reasons before it decides.

**The challenge.** UnderCover is the course's travel-insurance company. Its claims agent reads a claim and records a decision (approve, decline, or refer to a colleague) with a payout. A claim counts as right only when both the decision and the payout (to within $1) match what a human claims handler decided. The Day 2 challenge: get at least 15 of the 25 claims right on every run, as cheaply as possible, then push for more.

**The result.** On Luna (`openai/gpt-6-luna` at `low` reasoning effort), my agent's worst run is 22 of 25 on the queue and 22 on the held-out set. The agent from the Day 2 lab ("the lab's agent" below) gets 17 on both. Mine costs about 30% less a run and makes about half as many model calls.

How to read the numbers:

- **Queue:** the lab's 25 claims (`data/claims.json`). I used them to build and tune the agent.
- **Tuning:** running the agent, reading the claims it got wrong, and changing its prompt and tools to fix them. Because the changes come from the queue's mistakes, the queue score can flatter the agent.
- **Held-out set:** 25 other claims with the same mix (`data/evals/held_out_claims.json`), never looked at while tuning. It shows whether the gains carry over to claims the agent hasn't seen.
- **Run:** one pass over the 25 claims. Each agent ran 3 times on each set. **Worst** is the lowest of the 3 runs, and it's the number that matters, because the challenge asks for 15 on every run. **Mean** is the average of the 3.

| Luna `low`, 3 runs each | Queue: worst / mean | Held-out: worst / mean | Cost per run (held-out) | Model calls per claim |
|---|---|---|---|---|
| The lab's agent | 17 / 17.7 | 17 / 17.0 | $0.0070 | 3.0 |
| Lean agent (version 6, short wording) | 22 / 23.3 | 22 / 23.0 | $0.0049 | 1.6 |

## The design

The lab's workflow is fixed: every claim needs its policy and a recorded decision. So code does what happens on every claim, and the agent keeps the decisions that depend on the claim. The final agent has two tools: the lab's `record_decision` and a new `calculate_payout`.

1. **Fixed steps move from tools into code.** The lab's agent calls `get_policy` on every claim to look up the customer's policy. Here, code puts the policy record in the prompt, along with the plan limits (waiting periods, per-item limit, deductible and maximums) and the customer's earlier claims. Code also counts the claims filed in the last 12 months, because the claims manual refers a customer's third claim in 12 months. `record_decision` has `return_direct=True`, so LangChain ends the run as soon as the decision is recorded, with no final "done" call. Fewer round trips save twice: each tool call is another model call, and each call resends the whole conversation.
2. **Code does the arithmetic.** `calculate_payout` follows section 10 of the policy wording (the contract with the customer), which sets out how to work out a payout. The model decides which items are eligible and how to group them (a pair of shoes is one item, not two), and the tool applies the limits, the deductible and the maximum. It stays a tool because it's only needed when approving.
3. **The agent gets the information it was missing.** The lab's agent sees only the wording, the policy and the claim. The system prompt adds three reminders of rules the wording states but models tend to miss: how to count items ("four shirts" is four items, each with its own per-item limit), which devices the Electronics Plus add-on covers, and that a delay letter must state the delay's cause. It also adds a summary of the claims manual, UnderCover's internal rulebook for what the wording leaves open, such as meals without receipts, repeat claims and wild animals (a loss to a wild animal is accidental loss, not theft, so no police report is needed). I also tested the history and the manual as tools the agent could call (versions 4b and 5b below). The final agent puts both in the prompt, which needs fewer calls.
4. **It reasons before it decides.** `record_decision` asks for the rationale before the decision. The model writes the arguments in order, so it now reasons before it commits.

Version 6 also uses the lab's short policy wording (about 800 words instead of 1,400). It kept the same worst run, and it's about 12% cheaper once the provider has cached the repeated prompt.

## How I got there

I started from the lab's agent and added one change at a time, on the same model, 3 runs each, judged on the worst run. The two "side branch" rows give the agent the same information as a tool instead of in the prompt. The next version builds on the row above them, not on the side branch.

| Version | Worst | Mean | Cost per run | Model calls per claim |
|---|---|---|---|---|
| 0 lab agent | 17 | 17.7 | $0.0073 | 3.0 |
| 1 fixed steps in code | 12 | 13.3 | $0.0031 | 1.0 |
| 2 + calculator | 17 | 17.7 | $0.0044 | 1.5 |
| 3 + reminders of rules in the wording | 18 | 18.7 | $0.0046 | 1.6 |
| 4a + history in the prompt | 15 | 17.7 | $0.0046 | 1.6 |
| 4b history as a tool (side branch) | 18 | 19.7 | $0.0060 | 2.3 |
| 5a + manual summary in the prompt | 20 | 20.7 | $0.0047 | 1.5 |
| 5b manual as a tool (side branch) | 21 | 21.7 | $0.0098 | 3.3 |
| 6 + fixes from the error analysis | 22 | 23.0 | $0.0047 | 1.6 |
| 6, short wording | 22 | 23.3 | $0.0047 | 1.5 |

What each version changes:

- **0 lab agent:** the Day 2 lab's agent, unchanged: `get_policy`, then `record_decision`, then a final "done" call.
- **1 fixed steps in code:** the policy in the prompt, and recording ends the run (The design, point 1).
- **2 + calculator:** the `calculate_payout` tool (point 2).
- **3 + reminders of rules in the wording:** the three reminders, written into the system prompt (point 3).
- **4a + history in the prompt:** the customer's earlier claims and 12-month count, added by code (point 1).
- **4b history as a tool:** the same history, from a `get_claim_history` tool the agent calls when it chooses.
- **5a + manual summary in the prompt:** the manual summary, written into the system prompt (point 3).
- **5b manual as a tool:** a `get_manual_section` tool that returns one section of the manual when the agent asks.
- **6 + fixes from the error analysis:** the three fixes below.
- **6, short wording:** version 6 with the lab's shorter policy wording.

Version 1's drop to 12 is explained under Takeaways.

Version 6 came from reading the claims 5a got wrong. Most of those mistakes came from the manual summary itself: it listed reasons to refer a claim but left out the manual's limits on them, so the agent referred claims it should have paid, or paid the wrong amount. Version 6 makes three fixes, each taken from the manual or the plan data, not from the handlers' decisions:

- The summary adds the missing limits: refer only for the listed reasons, ask for proof of value only for single items over $100, and pay meal receipts when there are any.
- Code adds the plan limits to the prompt, with an instruction to check the waiting period first.
- The rationale comes before the decision.

**Where the gain comes from.** Each set has three kinds of claim: 15 routine, 5 hard (tricky payout arithmetic, or a carrier letter that confirms a delay but not its cause) and 5 manual (they need the claims manual or the customer's history). On the held-out set, the whole gain is on the hard and manual claims. On routine claims the two agents score the same.

| Held-out, mean right over 3 runs | Routine (of 15) | Hard (of 5) | Manual (of 5) |
|---|---|---|---|
| Lean agent (version 6, short wording) | 14.0 | 5.0 | 4.0 |
| The lab's agent | 14.3 | 2.7 | 0.0 |

## Takeaways

- **Removing a round trip isn't free.** Version 1 dropped from 17 to 12. With the policy already in the prompt, the model had to decide in its very first reply. The lab's `get_policy` call had been giving it a step to think first. The calculator and rationale-first gave that thinking step back.
- **No model can apply rules it never sees.** The lab's agent got none of the 5 manual claims on either set, because those rules are only in the manual.
- **A summary needs the limits as well as the rules.** Version 5a's summary listed reasons to refer without their limits, and its routine score fell to 11.3 of 15 (the lab's agent: 14.0). Version 6 fixed it.
- **The held-out score matches the queue score,** so the gain isn't just a result of tuning on the queue.

## Not done

- I haven't searched for the cheapest model that runs version 6. With a worst run of 22 there's room for a cheaper one, and changing `ABLATION_MODEL` in the notebook tests it.
- Version 6's three fixes went in together, so their separate value isn't measured.
- 25 claims per set and 3 runs each are enough to trust a gap of 5 claims, not to rank versions a claim apart.

## Running it

The notebook is [week1day2_lean_agent.ipynb](week1day2_lean_agent.ipynb). It runs in the course environment with `OPENROUTER_API_KEY` in `.env`. Running every cell costs about $0.20 and takes about 20 minutes.
