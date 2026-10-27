# Status

Building the pilot from `docs/PLAN.md`.

- `backend/`: `GET /api/health`. Reference data (plans, policies, customers, handlers, company settings, the policy wording) loads read-only from `data/*.json` into memory at import (`backend/data.py`). Claim status lives in SQLite (`backend/undercover.db`, gitignored), seeded from `data/claims.json` on first use (`backend/db.py`). Operations: `list_claims`, `get_claim`, `get_policy_wording`, `decide_claim` (approve/decline/refer, moves an over-limit approval to `waiting for sign-off`), `record_step` (moves a claim from `waiting` to `in progress`), `list_claim_steps`, `sign_off_claim`, `pay_claim` (blocked until any required sign-off).
`get_agent_instructions` serves the agent's instructions (`backend/instructions.py`), read by both the agent and (from Phase 5) the dashboard.

- `agent/`: `run(claim_id, thread_id)` fetches its instructions from the backend, then uses three tools — `get_claim`, `get_policy_wording`, `decide_claim` — each of which also records a step, so the backend's step log reflects exactly what the agent did. Checked against the real model on the 5 `tiny` sample claims: see `docs/PLAN.md` phase 3.
- `dashboard/`: one page that shows whether the backend is up.
- `e2e/`: one test of that page.

Still to build: the dashboard's queue, claim, and instructions pages.
