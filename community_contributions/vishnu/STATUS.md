# Status

The claims pilot, built phase by phase from `docs/PLAN.md`.

## Built

- `backend/`: FastAPI on SQLite. Seeds itself from `data/` on first start (never `data/evals/` or `data/security/`). Read operations: `list_claims`, `get_claim`, `get_policy`, `get_claim_history`, `get_policy_wording`, `get_instructions`, `list_handlers`, plus `health`. Workflow operations: `start_claim`, `record_step`, `record_decision`, `pay_claim` and `sign_off_claim`. The backend enforces the sign-off rule: a payout over $1,000 moves the claim to waiting for sign-off, and `pay_claim` returns 409 until a handler signs off, which records the payment. The agent's instructions are in `backend/instructions.md`.
- `agent/`: the UnderCover Agent, LangChain's `create_agent` on OpenRouter (`openai/gpt-6-luna` with low reasoning, or `MODEL_NAME`; output capped at 8,000 tokens, with retries and backoff on rate limits). Its tools call the backend only: `get_claim`, `get_policy`, `get_claim_history`, `get_policy_wording`, `record_decision`, `pay_claim`. `run(claim_id, thread_id)` starts the claim, reads its instructions from `get_instructions`, and records each step as it goes. A refused call comes back to the agent as text, so it can recover.
- `dashboard/`: React Router pages styled to `docs/BRAND.md`: the queue (`/`) with counts per status, a claim (`/claims/:claimId`) with its story, items, documents, decision, payment, policy and history, and the agent's instructions (`/instructions`, read only). A claim page polls every two seconds until the agent gives its answer and shows its steps as a timeline; a claim waiting for sign-off has a panel to choose a handler and sign off. The queue polls while any claim is in progress. API types are in `dashboard/src/types.ts`.
- `e2e/`: Playwright tests of the queue, a sign-off and the instructions. They run on their own ports (backend 8001, dashboard 5174) and database (`backend/e2e.db`, reseeded on each run), so they never touch `npm run dev`.

## Run it

- `uv sync` and `npm install` install everything
- `npm run dev` starts the backend on port 8000 and the dashboard on port 5173
- `uv run -m agent` works every waiting claim in queue order; `uv run -m agent CLM-1001` works one claim. Both need the backend running and `OPENROUTER_API_KEY` in `.env`
- `uv run -m backend.seed` resets the database to the seed state
- `npm run check` runs every check

If an agent run fails partway, its claim stays in progress; reseed to reset it. The database is `backend/undercover.db`; set `UNDERCOVER_DB` to use another file.

## Not built yet

As `docs/SPEC.md` says: the claims manual, sign-in, real payments and messages to customers. The agent is not yet scored against `data/evals/`.
