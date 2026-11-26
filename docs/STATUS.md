# Status

The pilot is being built to `docs/PLAN.md`. Phases 1 to 5 are done.

- `backend/`: FastAPI on SQLite. The database `backend/undercover.db` is created from `data/` on first use (`UNDERCOVER_DB` changes the path). Read routes: claims, policy with plan, claim history, policy wording, agent instructions, handlers. Workflow routes: start a claim, record steps, record a decision, pay, and sign off. A payout over $1,000 waits in `awaiting_signoff` and the backend refuses to pay it until a handler signs off.
- `agent/`: the UnderCover Agent, `create_agent` on OpenRouter with one tool per backend operation. Its instructions come from the backend (`backend/instructions.md`), and each tool call and result is posted to the backend as a step.
- `dashboard/`: React pages for the queue (counts by state and every claim), each claim in full with its decision and policy, and the agent's instructions, read only. Hash routes: `#/`, `#/claims/CLM-1001`, `#/instructions`. Light and dark mode follow the system setting. The queue and the claim page refresh every two seconds, so the agent's steps appear as it works. A claim waiting for sign-off has a panel where a handler signs off and releases the payment.
- `e2e/`: Playwright tests on their own backend (port 8001, database `e2e/e2e.db`, rebuilt each run) and dashboard (port 5174), so they never touch the dev database. They drive the API as the agent would, with no model calls.

## Commands

- `npm run dev`: backend on port 8000 and dashboard on 5173
- `uv run -m agent`: work every waiting claim in queue order (the backend must be running)
- `uv run -m agent CLM-1001`: work one claim
- `uv run -m backend.reset`: rebuild the database from `data/`
- `npm run check`: every check
