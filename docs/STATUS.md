# Status

The pilot is being built from `docs/PLAN.md`. Done so far: Phases 1 to 5.

- `backend/`: FastAPI on SQLite. The database is seeded from `data/` (never `data/evals/`) and serves the claims queue, policies with their plan limits, customers' claim history, the policy wording, the agent's instructions and the handlers. It records decisions, payments, sign-offs and the agent's steps, and enforces the rules: an approval over $1,000 waits for a handler's sign-off before it can be paid.
- `agent/`: the UnderCover Agent. `run(claim_id, thread_id)` starts the claim, fetches its instructions from the backend (`backend/instructions.md`), reads the claim, policy, claim history and policy wording through the API, records a decision and pays approvals up to $1,000. Each step is posted to the backend.
- `dashboard/`: React in the UnderCover brand, light and dark. The queue with a count per state; each claim in full with its policy, claim history, the agent's decision and reasons, and its steps live while it works (Run agent starts it); sign-off and payment for payouts over $1,000; and the agent's instructions read only. Views are hash links: `#/`, `#/claims/<id>`, `#/instructions`.
- `e2e/`: one test of that page

## Running it

- `uv sync` and `npm install` once
- `npm run seed` rebuilds the database at `backend/undercover.db` (or the path in `UNDERCOVER_DB`). The backend seeds it on startup if it is missing.
- `npm run dev` starts the backend on port 8000 and the dashboard on port 5173
- `uv run -m agent CLM-1001` runs the agent on one waiting claim, with the backend running
- `npm run check` runs every check
