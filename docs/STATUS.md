# Status

Built so far, toward the harness (`docs/PLAN_HARNESS.md`):

- `backend/`: FastAPI and SQLite. Seeds from `data/` (never `data/evals/`). Claims, decisions, payments with the $1,000 sign-off rule, runs with a cap and a to-do list, steps on every claim, retries (a claim that fails twice is left for a handler), claims manual and policy wording by section, and the instructions served from `backend/instructions/`.
- `agent/`: a queue agent (to-do list, cap, retries, missed-claim check) that hands each claim to a fresh claim agent. Default model `deepseek/deepseek-v4.1-flash`. Run: `npm run agent -- --limit 5` or `npm run agent -- --claim CLM-1001` (reseed first with `npm run reseed`).
- `dashboard/`: still the hello-world page.

Run: `npm run dev` starts the backend and the dashboard. `uv run -m backend.reseed` resets the data. `npm run check` runs every check.
