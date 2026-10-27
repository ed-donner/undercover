# Status

Building the pilot from `docs/PLAN.md`.

- `backend/`: `GET /api/health`. Reference data (plans, policies, customers, handlers, company settings, the policy wording) loads read-only from `data/*.json` into memory at import (`backend/data.py`). Claim status lives in SQLite (`backend/undercover.db`, gitignored), seeded from `data/claims.json` on first use (`backend/db.py`). Operations: `list_claims`, `get_claim`, `get_policy_wording`, `decide_claim` (approve/decline/refer, moves an over-limit approval to `waiting for sign-off`), `record_step` (moves a claim from `waiting` to `in progress`), `list_claim_steps`, `sign_off_claim`, `pay_claim` (blocked until any required sign-off).
`get_agent_instructions` serves the agent's instructions (`backend/instructions.py`), read by both the agent and (from Phase 5) the dashboard.

- `agent/`: `run(claim_id, thread_id)` fetches its instructions from the backend, then uses three tools — `get_claim`, `get_policy_wording`, `decide_claim` — each of which also records a step, so the backend's step log reflects exactly what the agent did. Checked against the real model on the 5 `tiny` sample claims: see `docs/PLAN.md` phase 3.
- `dashboard/`: React Router, with `/` the claims queue (a table with status badges) and `/claims/:claimId` a claim's full page (story, items, policy, customer history, and — once decided — the decision). Brand fonts and colors from `docs/BRAND.md` apply globally, checked in light and dark mode.
- `e2e/`: a smoke test that the queue page lists the claims.

Still to build: running the agent from the dashboard with a live step log, the instructions page, and the sign-off/payment UI.
