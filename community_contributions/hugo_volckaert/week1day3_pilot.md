# Week 1 Day 3: the UnderCover pilot

My build of the pilot from `docs/SPEC.md`, planned in `docs/PLAN.md` and built in six phases with Claude Code.

The code: https://github.com/hvolckaert/undercover/tree/week1day3-hugo

## What it does

- **Backend:** FastAPI on SQLite, seeded from `data/` on first start and never reading `data/evals/` or `data/security/`. Each claim is `waiting`, `in_progress`, `waiting_for_signoff` or `decided`. An approved payout over the $1,000 limit in `data/company.json` waits for a handler's sign-off, and `pay_claim` returns 409 until then, so the rule holds even if the agent tries to pay.
- **Agent:** LangChain's `create_agent` with `openai/gpt-6-luna` at low reasoning effort, or `MODEL_NAME`. Its tools are thin wrappers over the API, it fetches its instructions from the backend, and each tool call and reply is posted back as a step. A run that fails or ends without a decision returns the claim to `waiting`.
- **Dashboard:** React and Vite in the UnderCover brand, light and dark. The queue with counts by state, each claim in full with the agent's steps polled live, a sign-off control for large payouts, and the instructions read only.
- **Checks:** `npm run check` runs 31 Python tests (99.6% coverage), 13 Vitest tests (99.3%) and 4 Playwright tests. The E2E tests run on their own ports against a fresh database and stand in for the agent through its API, so no test calls a model.

## Takeaways

- Planning in phases, each with its own checks and commit, made the review easy: I could read one phase at a time instead of one big diff.
- Putting the sign-off rule in the backend, not in the prompt, is what makes it safe: the agent can approve a $3,750 claim, but only a handler can release the payment.
- The agent approved CLM-1003 without checking for a pre-existing condition. Passing tests don't mean good decisions; that is what the evals are for.
- On Windows, other software can quietly hold ports 8000 and 5173 (a local service, and WSL in mirrored networking mode). Running the E2E tests on their own ports avoided chasing phantom failures.
