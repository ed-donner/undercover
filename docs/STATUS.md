# Status

Building the pilot from `docs/PLAN.md`.

## Done

**Phase 1: the data layer.** `backend/db.py` loads the claims queue, customers, policies, plans and handlers from `data/` into an in-memory SQLite database at startup (never `data/evals/`), reseeding fresh every time the backend starts. Every claim starts `waiting`.

- `GET /api/claims` — the queue.
- `GET /api/claims/{claim_id}` — one claim, with its customer and its policy (plan limits merged in).
- `GET /api/policy-wording` — the policy wording text.
- `GET /api/handlers` — the claims handlers.

**Phase 2: deciding and paying a claim.** `backend/claims.py` holds the claim lifecycle:

- `POST /api/claims/{claim_id}/decide` — records a decision (approve/decline/refer). An approval leaves the claim open for payment; a decline or referral closes it.
- `POST /api/claims/{claim_id}/pay` — pays an approved claim, or holds it `waiting_for_sign_off` if the payout is over the $1,000 limit from `data/company.json`.
- `POST /api/claims/{claim_id}/sign-off` — a handler signs off a held claim, which releases its payment.
- `GET /api/claims/{claim_id}/events` — the step-by-step log of everything done to a claim, written by each of the above.

**Phase 3: the UnderCover Agent.** `agent/main.py` reads a claim and the policy wording, decides approve/decline/refer, and (if it approved) tries to pay — all through the backend's API, never touching `data/` directly. Its instructions live in `backend/agent_instructions.md`, served read-only at `GET /api/agent-instructions` and used as the agent's own system prompt, so the two can never drift apart. `POST /api/claims/{claim_id}/run` is the trigger: it moves a `waiting` claim to `in_progress` and calls the agent.

## Not built yet

The dashboard, and wiring it end to end. See `docs/PLAN.md` for the rest of the pilot.

## Running it

`npm run dev` starts the backend (`http://localhost:8000`) and the dashboard (`http://localhost:5173`). `npm run check` runs every check.
