# Sefa Ilyas Oz: the UnderCover pilot

My Week 1 Day 3 build for Ed Donner's course, AI FDE: The Forward Deployed Engineer & Agentic AI Architect.

- Build: https://github.com/sefailyasoz95/undercover/tree/week1day3-sefailyasoz
- Plan: [PLAN.md](PLAN.md), a copy of `docs/PLAN.md`

## What I did

1. Asked Claude Code to plan the pilot from the documents in `docs/`. It wrote `docs/PLAN.md` with six phases, each with success criteria it could check itself.
2. Reviewed the plan, then asked it to implement it. Each phase was tested and committed on its own, through the pre-commit hook, never with `--no-verify`.
3. Ran the real model on two claims, on both sides of the $1,000 limit, and watched them in the dashboard.

## Choices in the plan

- **The backend owns the rules.** `pay_claim` refuses a payout over the limit in `company.json` until a handler signs off, and signing off makes the payment. The agent cannot get around it.
- **The answer key stays out of reach.** The backend seeds only the files it names in `data/`, so `data/evals/` is never loaded, and the agent reaches everything through the API.
- **No contact details for the agent.** It gets the customer's claim history, not their email, phone or address.
- **Every step is recorded.** The agent posts each tool call, result and reply to the backend, and the dashboard polls them every two seconds while it works.
- **No claim gets stuck.** A run that crashes or ends without a decision refers the claim.
- **The end-to-end tests have their own world:** their own ports and a fresh database, so they never touch the dev data.

## What was built

- **Backend:** FastAPI on SQLite with the plain `sqlite3` module, 16 operations.
- **Agent:** `create_agent` on OpenRouter with six tools, each one backend call, and its instructions fetched from the API.
- **Dashboard:** React with hash routing: the queue with a count per state, the claim view with live steps and sign-off, and the instructions read only. Styled to `BRAND.md` in light and dark.

## Checks

- Python: ruff and pyright clean, 46 tests, 96% coverage.
- Dashboard: Prettier, ESLint and tsc clean, 17 tests, 99% coverage.
- End-to-end: 4 Playwright tests. No test calls a model.

## A real run

| Claim | Payout | Result |
|---|---|---|
| CLM-1001 | $420.00 | Paid at once |
| CLM-1003 | $3,750.00 | Held ($3,800 less the $50 deductible), then signed off by Priya Raman in the dashboard |

The first live run on CLM-1001 failed. The model called all four read tools in parallel and guessed the policy id (`CLM-1001`) before it had read the claim. The stub tests could not catch it. The fix was in the tools, not the prompt: `get_policy` and `get_claim_history` take no ids and look them up from the claim, which also stops the agent reading another customer's data. The fallback referred that claim, so nothing was left stuck.

## Takeaways

1. **A stub model doesn't test the model.** Every test was green and the first real run still failed. One real run is worth its few cents.
2. **Put the rule where the model can't break it.** Instructions describe the $1,000 sign-off; the backend enforces it.
3. **Narrow tools beat careful prompting.** Binding the tools to the claim removed a whole class of mistakes instead of asking the model not to make them.
4. **A plan with checkable criteria makes a fast build reviewable.** I could follow each phase and its commit.

## Not done

I did not score the agent against the handlers' decisions, and `data/evals/` was never opened.
