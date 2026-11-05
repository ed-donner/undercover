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

**Phase 4: the dashboard.** React Router with three pages, styled to `docs/BRAND.md` (Instrument Sans/Serif, JetBrains Mono, the brand palette, light and dark surfaces):

- **Queue** (`/`) — every claim, with a Run button on each waiting one.
- **Claim detail** (`/claims/:id`) — the story, items, documents, customer, policy, the decision once made, the step-by-step event log, and a sign-off control when a claim is waiting for one.
- **Instructions** (`/instructions`) — the agent's instructions, rendered from the same Markdown the agent reads.

"Run" and "Sign off" are wired to the backend, and the Queue and Claim detail pages poll while a claim is `waiting`/`in_progress` so its status and event log update live.

**Phase 5: wired end to end.** `e2e/` has Playwright tests for the queue, a claim's detail page and the sign-off flow (seeded through the backend's own API, never through a model). Verified by hand against a running `npm run dev` with the real agent: CLM-1001 (a routine trip delay) runs straight through to paid, and CLM-1003 (an emergency medical claim over $1,000) runs to `waiting_for_sign_off` and completes once signed off.

That manual run surfaced a real bug: `backend/db.py`'s shared SQLite connection wasn't safe for concurrent requests from multiple threads (the dashboard fires several requests on page load), causing intermittent 404s and 500s. Fixed by serializing every query - reads included, not just writes - through one lock; `backend/tests/test_db.py` has two regression tests for it.

## Not built yet

The final review against `docs/SPEC.md` (Phase 6 of `docs/PLAN.md`). Every feature in the spec is built.

## Running it

`npm run dev` starts the backend (`http://localhost:8000`) and the dashboard (`http://localhost:5173`). `npm run check` runs every check.
