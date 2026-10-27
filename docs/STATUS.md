# Status

Building the pilot from `docs/PLAN.md`.

- `backend/`: `GET /api/health`. Reference data (plans, policies, customers, handlers, company settings, the policy wording) loads read-only from `data/*.json` into memory at import (`backend/data.py`). Claim status lives in SQLite (`backend/undercover.db`, gitignored), seeded from `data/claims.json` on first use (`backend/db.py`). Operations: `list_claims` (the queue, oldest first), `get_claim` (one claim merged with its policy and its customer's previous claims), `get_policy_wording`.
- `agent/`: the entry point `run(claim_id, thread_id)`, with one tool that calls the health route. Not yet wired to the claim data.
- `dashboard/`: one page that shows whether the backend is up.
- `e2e/`: one test of that page.

Still to build: the agent's decision tools, the sign-off and payment rules, and the dashboard's queue, claim, and instructions pages.
