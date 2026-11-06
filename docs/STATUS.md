# Status

The pilot from `docs/PLAN.md` is built: a backend, the UnderCover Agent and a dashboard for the handlers. The harness from `docs/PLAN_HARNESS.md` is being built, and its phases are ticked off there as they're done.

- `backend/`: FastAPI on SQLite. The database is `backend/undercover.db`, or the path in `UNDERCOVER_DB`. The backend seeds it from `data/` when it starts without one, and never reads `data/evals/` or `data/security/`.
  - Read operations: `list_claims`, `get_claim`, `get_policy` (with the plan's limits and add-ons), `get_customer`, `list_handlers`, `get_policy_wording`, `list_sections`, `search_documents`, `read_section`, `get_instructions`, `list_steps` and `health`. The workflow: `start_claim`, `add_step`, `record_decision`, `pay_claim` and `sign_off`.
  - A claim is `waiting`, `in_progress`, `waiting_for_sign_off` or `decided`. A decline or referral is decided at once. An approval of $1,000 or less stays in progress until the agent pays it, and an approval over $1,000 waits for sign-off.
  - `pay_claim` pays only an approved claim's exact payout, once, and refuses a payout over $1,000 with `403`, whatever the agent does. A handler's `sign_off` pays those.
  - `backend/documents.py` splits the policy wording (12 sections) and the claims manual (14) at their numbered headings. `search_documents` is a keyword search that returns the five best sections with their best-matching lines, with rare words counting most.
  - The agent's instructions are `backend/instructions.md`.
- `agent/`: the UnderCover Agent, on LangChain's `create_agent` with GPT-6 Luna at low reasoning through OpenRouter, or the model in `MODEL_NAME`.
  - `run(claim_id, thread_id)` fetches the instructions from the backend, starts the claim and posts each step to the backend as it goes.
  - Its tools each call one API operation: `get_claim`, `get_policy`, `get_customer` (name, customer since and earlier claims only, so no personal details reach the model), `list_sections`, `search_documents` and `read_section` (it looks up the wording and the manual instead of reading them whole), `record_decision` and `pay_claim`. A refusal from the backend goes back to the model as the tool's result.
- `dashboard/`: React, Vite and TypeScript in the UnderCover brand, with light and dark mode following the system setting. Routing is by the URL's hash, and the dev server proxies `/api` to the backend in `BACKEND_URL`, by default port 8000.
  - The queue (`#/`) counts the claims in each status and lists every claim, refreshing every 2 seconds.
  - A claim (`#/claims/CLM-1001`) shows the agent's decision, reason, policy section and payment, the claim with its items and documents, the agent's steps as they happen (with any refusal from the backend marked), the policy, and the customer with their earlier claims. A claim waiting for sign-off has a form to choose a handler and sign off, which pays it.
  - The agent's instructions (`#/instructions`), read only.
- `e2e/`: Playwright tests of the queue, a claim page, live steps, sign-off and the instructions. They start their own backend on port 8001, freshly seeded into a database in the system's temp folder, and their own dashboard on port 5174, so they never touch the queue in `npm run dev`.

## Running it

### Start

From the root of the repo, run:

```
npm run dev
```

This starts the backend on port 8000 and the dashboard at http://localhost:5173. Leave that terminal open while you use them.

### Stop

Press Ctrl+C in the terminal where `npm run dev` is running.

If the servers were started somewhere else, for example by your coding agent, stop whatever is listening on the two ports:

- Mac or Linux: `lsof -ti tcp:8000,5173 | xargs kill`
- Windows PowerShell: `Get-NetTCPConnection -LocalPort 8000,5173 -State Listen | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force }`

The queue is saved in `backend/undercover.db`, so stopping loses nothing.

### Other commands

- `uv run -m agent` works every waiting claim, one at a time. The backend must be running, so use a second terminal. `uv run -m agent CLM-1001 CLM-1004` works just those claims. This calls the model and spends on your OpenRouter key.
- `uv run -m backend.seed` resets the queue to the records in `data/`. A decided claim is final, so run this to work the queue again.
- `npm run check` runs every check. Its end-to-end tests start their own servers on other ports, so it's safe to run while `npm run dev` is up.

## Not built yet

What the pilot leaves out is listed at the end of `docs/PLAN.md`: sign-in, real payments, messages to customers, scoring against `data/evals/`, retrying a failed run, and screens for referred claims.
