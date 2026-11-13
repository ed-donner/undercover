# The UnderCover pilot

My Week 1 Day 3 build for Ed Donner's course, AI FDE: The Forward Deployed Engineer & Agentic AI Architect. I directed Claude Code as UnderCover's forward deployed engineer: it planned the pilot from `docs/SPEC.md`, I reviewed the plan, and it built it in six phases, one commit each.

My build: https://github.com/sefailyasoz95/undercover/tree/week1day3-sefailyasoz

The plan is [`docs/PLAN.md`](https://github.com/sefailyasoz95/undercover/blob/week1day3-sefailyasoz/docs/PLAN.md) on that branch.

## What was built

- **Backend:** FastAPI on SQLite with the plain `sqlite3` module, seeded only from the files it names in `data/`, so `data/evals/` is never loaded. The backend owns the rules: a payout over the limit in `company.json` is refused by `pay_claim` itself until a handler signs off, and signing off makes the payment.
- **Agent:** `create_agent` with six tools, each one backend call. It fetches its instructions from the API, posts every step to the backend as it works, and refers the claim if a run ends without a decision.
- **Dashboard:** React with hash routing and no router library: the queue with a count per state, a claim view with live steps and sign-off, and the read-only instructions.
- **Tests:** 46 pytest, 17 vitest and 4 Playwright tests, none of which call a model. The end-to-end run has its own ports and a fresh database, so it never touches the dev data.

## Takeaways

- **The first live run found a bug the stub tests could not.** The model called all four read tools in parallel and guessed the policy id before it had read the claim, so the run failed with a 404. The fix was to bind the tools to the claim: `get_policy` and `get_claim_history` take no ids and look them up from the claim. That also stops the agent from reading another customer's data.
- **Put the rule where the agent can't argue with it.** The prompt tells the agent about the $1,000 sign-off, but the backend is what enforces it. In a live run the agent approved $3,750.00 on a medical claim, the payment was held, and it went through only after a handler signed off in the dashboard.
- **A fallback keeps the queue honest.** A run that crashes or ends without a decision refers the claim instead of leaving it stuck in progress.
