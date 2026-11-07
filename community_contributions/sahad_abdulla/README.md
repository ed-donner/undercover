# Week 1 Day 2: the cheapest consistent agent, and how sure we can be

The assignment asks for the cheapest model that *consistently* gets 15 of 25 claims right with the agent. This notebook measures "consistently" instead of assuming it: a Wilson lower bound on the pass rate, an estimate of the chance of reaching the target built from each claim's own hit rate, and a stability map of claims against models.

- `week1day2_how_sure.ipynb`: the lab's agent, unchanged, on any OpenRouter model. `FREE = True` runs `:free` models on the five tiny claims. `FREE = False` runs the paid study on all 25, for about $0.30. It also builds a leaderboard of 9 cheap models measured in the lab's agent (runs published in `community_contributions` plus its own paid screen), and a capability check of 8 models from cheap to frontier.
- `how_sure_results_free.csv`: every claim of every free run. The notebook carries on from it, so the study can build up over several days within the free limit.
- `capability_decisions.csv`: one run on all 25 claims by eight models, each given the lab's instructions, the policy wording and every claim in a single prompt with no tools (Grok 4.6, Gemini 3.8 Flash, Claude Sonnet 5.5, GPT-6 Luna, Claude Haiku 5.5, GPT-5.6 Luna, MAI Code 1.1 Flash, Claude Haiku 4.5), given no handler decisions and scored with the lab's check.

**Answer:** the cheapest model with strong evidence of reaching 15 of 25 consistently is the lab's Luna at `low`, about $0.009 a run: 5 runs out of 5, a 90% lower bound of 0.65. Ling 3.0 Flash is a little cheaper but missed on one run in four.

**Findings:** a single run can't show consistency, price is not quality (Haiku 4.5 costs 10 times Luna and scored 11), and the misses come in three kinds, each with its own fix. Random misses show up when you run more. Capability misses (CLM-1021, overpaid by every cheaper model and right for every stronger one) need a stronger model or a payout tool. Context misses (all five `manual` claims, missed by every model) need the claims manual in context.
