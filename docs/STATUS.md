# Status

The claims pilot, built from `docs/PLAN.md`. Phases 1 and 2 of 6 are done.

- `backend/`: FastAPI and SQLite. The database (`backend/undercover.db`, or `UNDERCOVER_DB`) is seeded from `data/` on first start, leaving out `data/evals/`. Read operations: `list_claims`, `get_claim`, `get_policy`, `get_claim_history`, `get_policy_wording`, `get_instructions`, `list_handlers`. Write operations: `add_step`, `list_steps`, `record_decision`, `pay_claim`, `sign_off`. A payout over $1,000 waits for a handler's sign-off, and `pay_claim` refuses it until then
- `agent/`: the skeleton's entry point `run(claim_id, thread_id)`, with one tool that calls the health route
- `dashboard/`: one page that shows whether the backend is up
- `e2e/`: one test of that page

## Running it

- `npm run dev` starts the backend on port 8000 and the dashboard on port 5173
- `uv run -m backend.db --reset` rebuilds the database from `data/`
