# Status

Built from `docs/PLAN.md`, phase by phase.

## Done

- Phase 1, backend data and read operations: `backend/` serves the claims queue, policies, customer history, policy wording, instructions and handlers from SQLite, seeded from `data/` on first start. The agent sees no contact details for customers.

- Phase 2, claim workflow and payment rule: start, decision, payment, sign-off and steps. `pay_claim` refuses with a 409 unless the claim has an approved decision, the amount equals the payout, it is unpaid and, over $1,000, a handler has signed off. A sign-off records the payment.

- Phase 3, the agent: `agent/main.py` has six tools over the backend API, fetches its instructions from the backend and records each step as it works. `uv run -m agent.main CLM-1001` runs it on one claim, and the backend's `run_claim` and `run_queue` run it in the background. Tests use a stub model. It has not yet been run against a real model.

## Still to build

The dashboard and the end-to-end tests. The `agent/` and `dashboard/` folders are still the hello-world skeleton.

## Run it

- `uv sync` and `npm install` once.
- `npm run dev` starts the backend on port 8000 and the dashboard on port 5173.
- `npm run check` runs every check.
- The database is `backend/undercover.db`, created on first start. Delete it to reset the queue.
