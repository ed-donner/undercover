# Week 1 Day 3: the UnderCover pilot

My build of the pilot, planned and built with Claude Code from `docs/SPEC.md`.

The code is on my fork: https://github.com/marcusmayo/undercover/tree/week1day3-ed

## What it does

- **Backend:** FastAPI on SQLite, seeded from `data/` without reading `data/evals/`. The rules are enforced in code, not in the prompt: one decision per claim, a payment only for the approved payout, and a payout over $1,000 can't be paid until a handler signs off, even if the agent tries.
- **Agent:** LangChain's `create_agent` on OpenRouter. It reads the claim, policy, claim history and policy wording only through the API, records a decision and pays approvals up to $1,000. Its instructions are served by the backend, so the dashboard shows exactly what the agent gets. Each step is posted to the backend as it happens.
- **Dashboard:** React and Vite in the UnderCover brand, light and dark. The queue with a count per state, each claim in full with the agent's decision, reason and policy section, its steps live while it works, and sign-off for large payouts. It refreshes on its own.
- **Checks:** 49 Python tests, 20 dashboard tests and 5 Playwright tests. The end-to-end tests run their own backend and database and play the agent's part through the API, so no test calls a model.

## Running the whole queue

I ran the agent on all 25 claims with `openai/gpt-6-luna`: 16 approved, 6 declined and 3 referred, with two approvals over $1,000 waiting for sign-off. I haven't scored these against the handlers' decisions in `data/evals/` yet.

## What I learned

- **Put the rules in the backend.** In the real runs the agent never tried to pay over the limit, but if it does the backend refuses, and the tests prove it. The rule holds whatever the model does.
- **Watch the real runs.** The tests passed, but real runs found three problems: the model guessed policy ids before reading the claim, the dashboard didn't refresh while a batch ran, and the agent once wrote its decision in its reply without calling `record_decision`, leaving the claim stuck in progress. The fixes were a line in the instructions, polling in the dashboard, and moving the clean-up into the agent's runner so a run that ends without a decision puts the claim back in the queue.
- **Plan, then review.** Writing the plan first, with checkable criteria for each phase, made it easy to see what was left and to verify each phase before moving on.
