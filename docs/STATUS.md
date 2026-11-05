# Status

Building the pilot from `docs/PLAN.md`.

## Done

**Phase 1: the data layer.** `backend/db.py` loads the claims queue, customers, policies, plans and handlers from `data/` into an in-memory SQLite database at startup (never `data/evals/`), reseeding fresh every time the backend starts. Every claim starts `waiting`.

- `GET /api/claims` — the queue.
- `GET /api/claims/{claim_id}` — one claim, with its customer and its policy (plan limits merged in).
- `GET /api/policy-wording` — the policy wording text.
- `GET /api/handlers` — the claims handlers.

## Not built yet

Deciding and paying a claim, the agent, the dashboard, and wiring it end to end. See `docs/PLAN.md` for the rest of the pilot.

## Running it

`npm run dev` starts the backend (`http://localhost:8000`) and the dashboard (`http://localhost:5173`). `npm run check` runs every check.
