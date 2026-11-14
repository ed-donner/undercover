# Status

The pilot is being built from `docs/PLAN.md`. Done so far: Phases 1 and 2.

- `backend/`: FastAPI on SQLite. The database is seeded from `data/` (never `data/evals/`) and serves the claims queue, policies with their plan limits, customers' claim history, the policy wording, the agent's instructions and the handlers. It records decisions, payments, sign-offs and the agent's steps, and enforces the rules: an approval over $1,000 waits for a handler's sign-off before it can be paid.
- `agent/`: the hello-world skeleton, `run(claim_id, thread_id)`
- `dashboard/`: one page that shows whether the backend is up
- `e2e/`: one test of that page

## Running it

- `uv sync` and `npm install` once
- `npm run seed` rebuilds the database at `backend/undercover.db` (or the path in `UNDERCOVER_DB`). The backend seeds it on startup if it is missing.
- `npm run dev` starts the backend on port 8000 and the dashboard on port 5173
- `npm run check` runs every check
