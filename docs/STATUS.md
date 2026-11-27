# Status

The claims pilot is built, from `docs/PLAN.md` (all six phases done).

## What's built

- `backend/`: FastAPI on SQLite. On first start it creates the database and seeds it from six files in `data/` and the policy wording. It never reads `data/evals/` or `data/security/`.
  - Read routes: claims, policies (with their plan's limits and add-ons), customers with their claim history, the policy wording, the handlers and the agent's instructions (`backend/instructions.md`).
  - Write routes: `run_agent`, `start_claim`, `release_claim`, `record_step`, `record_decision`, `pay_claim` and `sign_off`.
  - Claim states: `waiting`, `in_progress`, `awaiting_signoff`, `decided`.
  - The $1,000 rule is enforced here: `pay_claim` refuses a payout over the limit in `data/company.json` until a handler with `can_approve_over_limit` signs off, whoever calls it. Signing off makes the payment.
- `agent/`: `run(claim_id, thread_id)` decides one claim with LangChain's `create_agent` on OpenRouter (`openai/gpt-6-luna` with low reasoning effort, or `MODEL_NAME`).
  - It reaches everything through the backend's API. It reads its instructions, then the claim, the policy, the customer and the wording. It records a decision and pays when it approves.
  - The decision and payment tools are bound to the claim being run.
  - Each tool call, tool result and reply is posted as a step.
  - A failed run, or one that ends without a decision, puts the claim back to `waiting` with an error step.
- `dashboard/`: React, Vite and TypeScript, in the UnderCover brand, with light and dark modes. It has three screens:
  - the queue (`#/`), with a count of claims in each state
  - a claim (`#/claims/CLM-1001`), with its decision, reasons, calculation, policy, items and documents, a Run agent button, the agent's steps as it works, and a sign-off form for payouts over $1,000
  - the agent's instructions, read only (`#/instructions`)
- `e2e/`: Playwright tests of the dashboard. They run their own backend on port 8001 and dashboard on port 5174, on a fresh database in `e2e/test-results/`, so they never touch the development data. They act as the agent through the API, so they never call a model.

## Running it

- `npm run dev` starts the backend on port 8000 and the dashboard on http://localhost:5173.
- `uv run -m agent CLM-1001` runs the agent on one claim from the command line; the backend must be running.
- The database is `backend/undercover.db`, or the file named in `UNDERCOVER_DB`. Delete it to start again from the seed data.
- The dashboard polls: the queue every 3 seconds, a claim every 2 seconds, and its steps every second while the agent works.
- `npm run check` runs every check.

## The pilot run

Seven claims were run live on `openai/gpt-6-luna`, each in about 10 seconds, and checked against the policy wording (not against `data/evals/`, which hasn't been opened):

| Claim | Decision | Payout |
|---|---|---|
| CLM-1001 trip delay | approve | $420.00, paid |
| CLM-1002 baggage | approve | $580.00, paid |
| CLM-1003 emergency medical | approve | $3,750.00, waiting for sign-off |
| CLM-1004 baggage delay | approve | $74.00, paid; the dress was judged not essential |
| CLM-1005 passport | approve | $243.00, paid |
| CLM-1006 emergency medical | approve | $425.00, paid |
| CLM-1008 trip cancellation | approve | $2,240.00, paid after sign-off |

CLM-1002 was first referred for missing receipts, which the wording doesn't require for belongings. The instructions now say that a document is missing only when the wording names it for the benefit, and the rerun gave the right payout.

## Notes

- The agent calls the backend at `127.0.0.1:8000`, not `localhost`: on Windows `localhost` tries IPv6 first and adds about 2 seconds to every call.
- On Windows, stopping `npm run dev` can leave uvicorn worker processes holding port 8000 with old code. If the backend looks out of date, stop the Python processes started from this repo and start it again.
- Accuracy against the handlers' decisions in `data/evals/` hasn't been measured yet.
