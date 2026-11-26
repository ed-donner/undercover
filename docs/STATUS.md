# Status

The pilot is being built to `docs/PLAN.md`. Phases 1 to 3 are done.

- `backend/`: FastAPI on SQLite. The database `backend/undercover.db` is created from `data/` on first use (`UNDERCOVER_DB` changes the path). Read routes: claims, policy with plan, claim history, policy wording, agent instructions, handlers. Workflow routes: start a claim, record steps, record a decision, pay, and sign off. A payout over $1,000 waits in `awaiting_signoff` and the backend refuses to pay it until a handler signs off.
- `agent/`: the UnderCover Agent, `create_agent` on OpenRouter with one tool per backend operation. Its instructions come from the backend (`backend/instructions.md`), and each tool call and result is posted to the backend as a step.
- `dashboard/`: still the skeleton's health page

## Commands

- `npm run dev`: backend on port 8000 and dashboard on 5173
- `uv run -m agent`: work every waiting claim in queue order (the backend must be running)
- `uv run -m agent CLM-1001`: work one claim
- `uv run -m backend.reset`: rebuild the database from `data/`
- `npm run check`: every check
