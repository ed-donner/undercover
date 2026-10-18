# Status

The claims pilot is built to `docs/PLAN.md`, with one check outstanding: the agent has not been run against a real model (see below). `npm run check` passes.

## What is built

- `backend/`: FastAPI and SQLite, seeded from `data/` on first start (never from `data/evals/`). It serves claims, policies, customer history (no contact details), the policy wording, the agent's instructions and the handlers. It runs the claim workflow: start, decision, payment, sign-off and steps. `pay_claim` refuses with a 409 unless the claim has an approved decision, the amount equals the payout, it is unpaid and, over $1,000, a handler has signed off. A sign-off records the payment. `run_claim` and `run_queue` start the agent in the background.
- `agent/`: `create_agent` on OpenRouter with six tools over the backend's API. It fetches its instructions from the backend, starts the claim, and records each tool call, result and message as a step. `uv run -m agent.main CLM-1001` runs it on one claim. Tests use a stub model.
- `dashboard/`: the queue (status counts, filter, run buttons), the claim screen (the claim, the decision and its reasons, the agent's steps, the policy, the customer's history and the sign-off panel) and the read-only instructions. Light and dark, in the brand colors and fonts.
- `e2e/`: Playwright tests on their own ports (8100 and 5273) and a throwaway database. They stand in for the agent through the API.
- `backend/instructions.md`: the agent's instructions, shown in the dashboard.

## Not yet checked

The live run of the agent against a real model (Phase 3). The agent is tested with a stub model only. To try it: put `OPENROUTER_API_KEY` in `.env`, run `npm run dev`, then use Run agent on a claim in the dashboard, or `uv run -m agent.main CLM-1001`.

## Run it

- `uv sync` and `npm install` once.
- `npm run dev` starts the backend on port 8000 and the dashboard at http://localhost:5173.
- `npm run check` runs every check.
- The database is `backend/undercover.db`. Delete it to reset the queue.

## Notes

- The agent's payout arithmetic is its own. Nothing checks it, and accuracy against the handlers' decisions has not been measured.
- A claim whose agent run fails stays In progress, with an error step. Running the agent on it again is allowed from the command line; the dashboard's Run agent button is for waiting claims only.
