# Status

The claims pilot, built from `docs/PLAN.md`. Phases done: 1, 2, 3, 4, 5.

- `backend/`: FastAPI on SQLite. On first start it creates the database and seeds it from six files in `data/` and the policy wording; it never reads `data/evals/` or `data/security/`. Read-only routes for claims, policies (with their plan's limits and add-ons), customers, the policy wording and the handlers.
  The agent and the handlers change claims through `start_claim`, `release_claim`, `run_agent`, `record_step`, `record_decision`, `pay_claim` and `sign_off`. `pay_claim` refuses a payout over the $1,000 limit (from `data/company.json`) until a handler with `can_approve_over_limit` signs off. Claim states: `waiting`, `in_progress`, `awaiting_signoff`, `decided`.
  The agent's instructions are `backend/instructions.md`, served by `get_instructions`.
  `run_agent` marks a waiting claim in progress and runs the agent in a background thread.
- `agent/`: `run(claim_id, thread_id)` decides one claim with LangChain's `create_agent` on OpenRouter (`openai/gpt-6-luna`, or `MODEL_NAME`). It reaches everything through the backend's API: it reads its instructions, marks the claim in progress, reads the claim, policy, customer and wording, records a decision and pays. The decision and payment tools are bound to the claim being run. Each tool call, tool result and reply is posted as a step. A failed run, or one that ends without a decision, puts the claim back to `waiting` with an error step.
- `dashboard/`: React, Vite and TypeScript, in the UnderCover brand with light and dark modes. Three screens with hash links: the queue (`#/`) with a count of claims in each state, a claim in full with its decision, policy, items and documents (`#/claims/CLM-1001`), with a Run agent button on waiting claims, the agent's steps as it works, and a sign-off form for payouts over $1,000; and the agent's instructions, read only (`#/instructions`). `src/api.ts` is the typed API client.
- `e2e/`: Playwright tests of the dashboard. They run their own backend on port 8001 and dashboard on port 5174, on a fresh database in `e2e/test-results/`, so they never touch the development data.

## Running it

- `npm run dev` starts the backend on port 8000 and the dashboard on port 5173.
- The database is `backend/undercover.db`, or the file named in `UNDERCOVER_DB`. Delete it to start again from the seed data.
- `uv run -m agent CLM-1001` runs the agent on one claim; the backend must be running.
- The dashboard polls: the queue every 3 seconds, a claim every 2 seconds and its steps every second while the agent works.
- On Windows, stopping `npm run dev` can leave uvicorn worker processes holding port 8000 with old code. If the backend seems out of date, stop the python processes started from this repo and start it again.
