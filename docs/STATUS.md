# Status

The pilot is being built to `docs/PLAN.md`. Phase 1 is done.

- `backend/`: FastAPI on SQLite. The database `backend/undercover.db` is created from `data/` on first use (`UNDERCOVER_DB` changes the path). Read routes: claims, policy with plan, claim history, policy wording, agent instructions, handlers.
- `agent/`: still the skeleton's health-check agent
- `dashboard/`: still the skeleton's health page

## Commands

- `npm run dev`: backend on port 8000 and dashboard on 5173
- `uv run -m backend.reset`: rebuild the database from `data/`
- `npm run check`: every check
