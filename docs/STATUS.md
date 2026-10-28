# Status

The claims pilot from `docs/SPEC.md` is built, following `docs/PLAN.md` (all six phases done).

## What's built

- `backend/`: FastAPI and SQLite. The database (`backend/undercover.db`, or the file in `UNDERCOVER_DB`) is seeded from `data/` on first start, leaving out `data/evals/` and `data/security/`.
  - Read: `list_claims`, `get_claim`, `get_policy`, `get_claim_history` (earlier claims only, no personal details), `get_policy_wording`, `get_instructions`, `list_handlers`, `list_steps`
  - Write: `add_step`, `record_decision`, `pay_claim`, `sign_off`, `run_agent`, `run_queue`
  - Claim states: `waiting`, `in_progress`, `awaiting_sign_off`, `decided`. Approving a payout over $1,000 moves a claim to `awaiting_sign_off`, and `pay_claim` refuses it until a handler signs off. Signing off pays the claim.
  - `run_agent` and `run_queue` run the agent in a background task. A run that ends without a decision puts the claim back to `waiting` with an error step.
- `backend/instructions.md`: the agent's instructions, served by `get_instructions` and shown read only in the dashboard.
- `agent/`: the UnderCover Agent, `run(claim_id, thread_id)`, built with `create_agent` on OpenRouter (`openai/gpt-6-luna` with low reasoning effort, or `MODEL_NAME`). Its tools call the backend: `get_claim`, `get_policy`, `get_claim_history`, `get_policy_wording`, `record_decision` and `pay_claim`. It fetches its instructions from the backend and posts each tool call, result and reply as a step.
- `dashboard/`: React, Vite and TypeScript in the UnderCover brand, light and dark.
  - `#/`: the queue, with a count for each state and a Run the queue button
  - `#/claims/<id>`: the claim, its policy, the decision with its reason and section, the payment, a Run agent button, the agent's steps as it works, and sign-off by a handler for payouts over $1,000
  - `#/instructions`: the agent's instructions, read only
- `e2e/`: Playwright tests of the queue, the steps and decision on a claim, sign-off of a payout over $1,000, and the instructions. They run their own backend (port 8001, `e2e/test.db`, rebuilt each run) and dashboard (port 5174), and stand in for the agent through the API, so they never call a model.

## Running it

- `npm run dev` starts the backend on port 8000 and the dashboard on http://localhost:5173
- Open a claim and press Run agent, or press Run the queue. Each run calls the model in `MODEL_NAME`, or GPT-6 Luna by default; `MODEL_NAME=openrouter/free` in `.env` is free
- `uv run -m backend.db --reset` rebuilds the database from `data/`
- `npm run check` runs every check

## Notes

- Not used in the pilot, as the spec says: the claims manual. Also unused: `policy_wording_short.md`, `knowledge.json` and `security/`.
- The agent's accuracy hasn't been measured against `data/evals/`. In the live checks it approved and paid CLM-1001 ($420.00) and CLM-1002 ($580.00), declined CLM-1013 (under the 12-hour waiting period), referred CLM-1010 (whether the alcohol exclusion applies) and approved CLM-1008 ($2,240.00), which waited for sign-off.
