# Status

The pilot is being built from `docs/PLAN.md`. Done so far: Phase 1, the backend's records.

- `backend/`: FastAPI on SQLite. The database is `backend/undercover.db`, or the path in `UNDERCOVER_DB`. The backend seeds it from `data/` when it starts without one. Read operations: `list_claims`, `get_claim`, `get_policy` (with the plan's limits and add-ons), `get_customer`, `list_handlers`, `get_policy_wording` and `health`.
- `agent/`: the skeleton's entry point `run(claim_id, thread_id)`, with one tool that calls the health route
- `dashboard/`: the skeleton's page that shows whether the backend is up
- `e2e/`: one test of that page

## Running it

- `npm run dev` starts the backend on port 8000 and the dashboard on http://localhost:5173
- `uv run -m backend.seed` resets the queue to the records in `data/`
- `npm run check` runs every check
