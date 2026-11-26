# Status

The pilot is built: every phase of `docs/PLAN.md` is done.

## What's built

- `backend/`: FastAPI on SQLite. The database `backend/undercover.db` is created from `data/` on first use (`UNDERCOVER_DB` changes the path). It never reads `data/evals/`.
  - Read routes: claims in queue order, a claim in full, its policy with plan and add-ons, the customer's earlier claims (no contact details), the policy wording, the agent's instructions and the handlers.
  - Workflow routes: start a claim, record steps, record a decision, pay, and sign off.
  - Claim states: `waiting`, `in_progress`, `awaiting_signoff` and `decided`. An approved payout over $1,000 waits in `awaiting_signoff`, and the backend refuses to pay it until a handler signs off, which releases the payment.
- `agent/`: the UnderCover Agent, LangChain's `create_agent` on OpenRouter, with one tool per backend operation. It reaches claims and its instructions only through the API. Its instructions are in `backend/instructions.md`. It posts each step to the backend in plain words, and posts refusals in full. It uses `openai/gpt-6-luna` with low reasoning effort, or `MODEL_NAME` if set, and retries rate-limited model calls for about a minute.
- `dashboard/`: React pages for the queue (counts by state and every claim), each claim in full with its decision, policy and the agent's steps, and the agent's instructions, read only. Hash routes: `#/`, `#/claims/CLM-1001` and `#/instructions`. Light and dark mode follow the system setting. The queue and claim pages refresh every two seconds. A claim waiting for sign-off has a panel where a handler signs off and releases the payment.
- `e2e/`: Playwright tests on their own backend (port 8001, database `e2e/e2e.db`, rebuilt each run) and dashboard (port 5174), so they never touch the dev database. They drive the API as the agent would, with no model calls.

## Commands

- `npm run dev`: backend on port 8000 and dashboard on http://localhost:5173
- `uv run -m agent`: work every waiting claim in queue order (with the backend running)
- `uv run -m agent CLM-1001`: work one claim, or resume one a failed run left in progress
- `uv run -m backend.reset`: rebuild the database from `data/`, so every claim is waiting again
- `npm run check`: every check

## Not built yet

- Scoring the agent against `data/evals/`
- The claims manual, sign-in, real payments and messages to customers, which the spec leaves out of the pilot
