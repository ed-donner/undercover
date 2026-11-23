# Status

The pilot is built: a backend, a dashboard and the UnderCover Agent that works the claims queue.

A live run of the whole queue with `openai/gpt-6-luna` decided all 25 claims with no errors: 3 payouts over $1,000.00 (CLM-1003, CLM-1008, CLM-1011) are waiting for a handler's sign-off with no payment made, 9 other approvals are paid, and 13 claims were declined or referred. The results are in the database until `npm run reset`.

## What is built

- `backend/`: FastAPI and SQLite. On first start it loads `data/` into `backend/undercover.db` (ignored by git). It reads only the files named in `backend/seed.py`, never `data/evals/` or `data/security/`, and never the claims manual.
  - Reading: `list_claims`, `get_claim`, `get_claim_context` (leaves out the customer's contact details), `get_policy_wording`, `list_handlers`, `get_instructions`, `list_steps`, `get_run_status`.
  - Writing: `record_decision`, `pay_claim`, `sign_off_claim`, `record_step`, `start_claim_run`, `start_queue_run`.
  - The rule: a payout over the limit in `data/company.json` ($1,000.00) is refused by `pay_claim` until a handler signs it off with `sign_off_claim`. A payout of exactly $1,000.00 pays without sign-off.
  - A claim is waiting, in progress, waiting for sign-off, or decided. Declined and referred claims count as decided.
  - Runs: the agent runs in a background thread, one run at a time. A run that fails, or ends without a decision, leaves an error step and the claim goes back to waiting. A run cut off by a restart is marked failed when the backend starts.
- `agent/`: `run(claim_id, thread_id)` runs the agent on one claim. It fetches its instructions (`backend/instructions.md`) from the backend, reads the claim and the policy wording, records its decision and pays through the backend, and records each step as it goes. It uses `openai/gpt-6-luna`, or `MODEL_NAME` if set. It reaches the backend at `http://localhost:8000`.
- `dashboard/`: React, Vite and TypeScript, in the brand's fonts and colors, light and dark. Three screens: the queue (`#/`) with each claim's state, decision and payout, a claim (`#/claims/CLM-1001`) with its decision, payment, sign-off, steps and details, and the agent's instructions (`#/instructions`), read only. Pages refresh every two seconds while a run is active.
- `e2e/`: Playwright tests that run against their own backend (port 8100, `backend/e2e.db`) and dashboard (port 5174), reset when the tests start. They never call a model.

## Run it

1. `uv sync` and `npm install`, once. Put `OPENROUTER_API_KEY` in `.env`.
2. `npm run dev` starts the backend on port 8000 and the dashboard at http://localhost:5173.
3. Open the queue and press "Run the queue", or open a claim and press "Run the agent". Handlers sign off payouts over the limit on the claim page.
4. `npm run reset` puts the database back to the seed data. Stop the backend first if a run is active.
5. `npm run check` runs every check.

## Not done yet

- Scoring the agent against `data/evals/`. Not part of the pilot plan.
