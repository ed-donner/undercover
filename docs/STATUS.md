# Status

The pilot is being built from `docs/PLAN.md`. Done so far: Phases 1 to 5, the backend, the agent and the dashboard.

- `backend/`: FastAPI on SQLite. The database is `backend/undercover.db`, or the path in `UNDERCOVER_DB`. The backend seeds it from `data/` when it starts without one. Read operations: `list_claims`, `get_claim`, `get_policy` (with the plan's limits and add-ons), `get_customer`, `list_handlers`, `get_policy_wording`, `get_instructions`, `list_steps` and `health`. The workflow: `start_claim`, `add_step`, `record_decision`, `pay_claim` and `sign_off`.
  - A claim is `waiting`, `in_progress`, `waiting_for_sign_off` or `decided`. An approval of $1,000 or less stays in progress until it's paid.
  - `pay_claim` pays only an approved claim's exact payout, once, and refuses a payout over $1,000 with `403`. A handler's `sign_off` pays those.
  - The agent's instructions are `backend/instructions.md`.
- `agent/`: the UnderCover Agent, on LangChain's `create_agent` with GPT-6 Luna at low reasoning through OpenRouter, or the model in `MODEL_NAME`. `run(claim_id, thread_id)` fetches its instructions from the backend, starts the claim and posts each step to the backend as it goes. Its tools each call one API operation: `get_claim`, `get_policy`, `get_customer` (name, customer since and earlier claims only), `get_policy_wording`, `record_decision` and `pay_claim`. A refusal from the backend goes back to the model as the tool's result.
- `dashboard/`: React, Vite and TypeScript in the UnderCover brand, with light and dark mode following the system setting. Routing is by the URL's hash.
  - The queue (`#/`) counts the claims in each status and lists every claim, refreshing every 2 seconds.
  - A claim (`#/claims/CLM-1001`) shows the agent's decision, reason, policy section and payment, the claim with its items and documents, the agent's steps as they happen (with any refusal from the backend marked), the policy and the customer with their earlier claims. A claim waiting for sign-off has a form to choose a handler and sign off, which pays it.
  - The agent's instructions (`#/instructions`), read only. The dev server proxies `/api` to the backend in `BACKEND_URL`, by default port 8000.
- `e2e/`: Playwright tests of the queue, a claim page, live steps, sign-off and the instructions. They start their own backend on port 8001, freshly seeded into a database in the system's temp folder, and their own dashboard on port 5174, so they never touch the queue in `npm run dev`.

## Running it

- `npm run dev` starts the backend on port 8000 and the dashboard on http://localhost:5173
- `uv run -m agent` works every waiting claim, one at a time, with the backend running. `uv run -m agent CLM-1001 CLM-1004` works just those claims. This calls the model and spends on your OpenRouter key.
- `uv run -m backend.seed` resets the queue to the records in `data/`. A decided claim is final, so run this to work the queue again.
- `npm run check` runs every check
