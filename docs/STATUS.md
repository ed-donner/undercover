# Status

The pilot is being built to `docs/PLAN.md`. Phases 1 and 2 are done.

- `backend/`: FastAPI on SQLite. The database `backend/undercover.db` is created from `data/` on first use (`UNDERCOVER_DB` changes the path). Read routes: claims, policy with plan, claim history, policy wording, agent instructions, handlers. Workflow routes: start a claim, record steps, record a decision, pay, and sign off. A payout over $1,000 waits in `awaiting_signoff` and the backend refuses to pay it until a handler signs off.
- `agent/`: still the skeleton's health-check agent
- `dashboard/`: still the skeleton's health page

## Commands

- `npm run dev`: backend on port 8000 and dashboard on 5173
- `uv run -m backend.reset`: rebuild the database from `data/`
- `npm run check`: every check
