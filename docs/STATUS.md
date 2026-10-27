# Status

Building the pilot from `docs/PLAN.md`.

- `backend/`: `GET /api/health`. Reference data (plans, policies, customers, handlers, company settings, the policy wording) loads read-only from `data/*.json` into memory at import (`backend/data.py`). Claim status lives in SQLite (`backend/undercover.db`, gitignored), seeded from `data/claims.json` on first use (`backend/db.py`). Operations: `list_claims`, `get_claim`, `get_policy_wording`, `decide_claim` (approve/decline/refer, moves an over-limit approval to `waiting for sign-off`), `record_step` (moves a claim from `waiting` to `in progress`), `list_claim_steps`, `sign_off_claim`, `pay_claim` (blocked until any required sign-off).
- `agent/`: the entry point `run(claim_id, thread_id)`, with one tool that calls the health route. Not yet wired to the claim data.
- `dashboard/`: one page that shows whether the backend is up.
- `e2e/`: one test of that page.

Still to build: the agent's decision tools, and the dashboard's queue, claim, and instructions pages.
