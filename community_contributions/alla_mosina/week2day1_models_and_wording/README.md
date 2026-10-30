## Week 2 Day 1: models, reasoning and how to shorten the wording

My version of the Week 2 Day 1 lab. Ed's Parts 1 to 4 and his two experiments are unchanged. After them come three experiments of my own, each with its conclusions, on the 25 harder claims with the payout tool. Only the model, the reasoning level and the policy wording change: the instructions, the tools, the payout rules and the scoring are Ed's.

- **Experiment 3:** GPT-6 Luna at medium and high reasoning, Grok 4.6 at low, medium and high, and Grok 4.7 at low.
- **Experiment 4:** the assignment, Ed's concise wording against the full wording on Luna at three reasoning levels, with the cost of a wrongful decline scored again.
- **Experiment 5:** two ways to shorten the wording that keep its meaning, on Luna at medium reasoning.

### Results

One run of each, on October 29, 2026. Wrong means the decision or the payout differs from the handler's.

| Agent with the payout tool | Wrong of 25 | Cost of mistakes | Model cost per run |
|---|---|---|---|
| Ed's baseline, no payout tool, Luna, no reasoning | 14 | $9,775 | $0.008 |
| Luna, no reasoning | 3 | $1,583 | $0.011 |
| Luna, medium reasoning | 2 | $100 | $0.018 |
| Luna, high reasoning | 1 | $50 | $0.019 |
| Grok 4.6, low reasoning | 3 | $150 | $0.41 |
| Grok 4.6, medium reasoning | 0 | $0 | $0.72 |
| Grok 4.6, high reasoning | 0 | $0 | $0.85 |
| Grok 4.7, low reasoning | 3 | $150 | $0.54 |
| Luna, medium, Ed's concise wording | 4 | $1,928 | $0.017 |
| Luna, medium, only the sections each claim needs | 0 | $0 | $0.017 |

### What I found

- **Low reasoning confuses "needs sign-off" with "refer".** All six mistakes of Grok at low reasoning are approvals over $1,000 that the agent worked out to the cent and then referred, because the payout tool returned `needs_sign_off: true`. The lab's instructions don't say that an approval over $1,000 is held for sign-off, not referred.
- **Ed's concise wording loses meaning in a few places.** "scuba below 10 meters", for the full wording's "deeper than 10 meters", led Luna to decline a dive to 9 meters at both medium and high reasoning, and "Adventure Sports covers", for "Adventure sports are", left grade 3 rafting unclear. With reasoning on, it made 3 more mistakes than the full wording and saved nothing.
- **Shorten by choosing, not by rewriting.** A rewrite that copies every definition, threshold and example word for word, in `week2day1_policy_wording_short_v2.md`, fixed those mistakes but is only 13% shorter. Giving each claim only the sections of the full wording it needs cuts 40% to 50% without changing a word, and was the one run of Luna with no mistakes. Section 8 has to go into every claim, because it defines adventure sports and electronics.
- **Shortening doesn't save money on Luna.** Most of the wording is read from the provider's cache at about a tenth of the price, so every wording costs 1.6 to 1.7 cents a run. Most of the cost is the tokens the model writes.
- **One run is noise.** Luna at medium and high swapped places between two runs each, so I'd take medium. Check any of these with `N_TIMES = 3` before relying on it.

### Files and running it

The new concise wording is in `week2day1_policy_wording_short_v2.md`. The note at its top lists every change from Ed's `data/policy_wording_short.md`, which is not changed, and the notebook strips the note before the wording goes into the prompt. `results_summary_2026-10-29.csv` has one row for each of my runs, with its mistakes and what they and the model cost.

The notebook runs from this folder on the `.venv` kernel, with `OPENROUTER_API_KEY` and the Langfuse keys in `.env`, like the lab. Experiment 3 calls Grok, which costs about 20 times more per token than Luna, so a full run costs about $3 and takes about an hour and a half. Taking the Grok rows out of `MODELS` brings it to about 20 cents.
