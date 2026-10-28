# Status

The claims pilot, built from `docs/PLAN.md`. Phase 1 of 6 is done.

- `backend/`: FastAPI and SQLite. The database (`backend/undercover.db`, or `UNDERCOVER_DB`) is seeded from `data/` on first start, leaving out `data/evals/`. Read operations: `list_claims`, `get_claim`, `get_policy`, `get_claim_history`, `get_policy_wording`, `get_instructions`, `list_handlers`
- `agent/`: the skeleton's entry point `run(claim_id, thread_id)`, with one tool that calls the health route
- `dashboard/`: one page that shows whether the backend is up
- `e2e/`: one test of that page

## Running it

- `npm run dev` starts the backend on port 8000 and the dashboard on port 5173
- `uv run -m backend.db --reset` rebuilds the database from `data/`
