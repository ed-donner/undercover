# Status

The claims pilot, built from `docs/PLAN.md`. Phases done: 1, 2.

- `backend/`: FastAPI on SQLite. On first start it creates the database and seeds it from six files in `data/` and the policy wording; it never reads `data/evals/` or `data/security/`. Read-only routes for claims, policies (with their plan's limits and add-ons), customers, the policy wording and the handlers.
  The agent and the handlers change claims through `start_claim`, `release_claim`, `record_step`, `record_decision`, `pay_claim` and `sign_off`. `pay_claim` refuses a payout over the $1,000 limit (from `data/company.json`) until a handler with `can_approve_over_limit` signs off. Claim states: `waiting`, `in_progress`, `awaiting_signoff`, `decided`.
  The agent's instructions are `backend/instructions.md`, served by `get_instructions`.
- `agent/`: still the hello-world skeleton.
- `dashboard/`: still the skeleton page that shows whether the backend is up.
- `e2e/`: one test of that page.

## Running it

- `npm run dev` starts the backend on port 8000 and the dashboard on port 5173.
- The database is `backend/undercover.db`, or the file named in `UNDERCOVER_DB`. Delete it to start again from the seed data.
