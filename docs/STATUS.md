# Status

The pilot from `docs/PLAN.md` is built: all six phases.

- `backend/`: FastAPI on SQLite. The database is seeded from `data/` (never `data/evals/`) and serves the claims queue, policies with their plan limits, customers' claim history (without personal details), the policy wording, the agent's instructions (`backend/instructions.md`) and the handlers. It records decisions, payments, sign-offs and the agent's steps, and enforces the rules: one decision per claim, a payment only for the approved payout, and an approval over $1,000 waits for a handler's sign-off before it can be paid.
- `agent/`: the UnderCover Agent. `run(claim_id, thread_id)` starts the claim, fetches its instructions from the backend, reads the claim, policy, claim history and policy wording through the API, records a decision and pays approvals up to $1,000. Each step is posted to the backend. If a run fails or ends without recording a decision, the runner puts the claim back to waiting (through `release_claim`) with the problem shown as a step, however the run was started.
- `dashboard/`: React in the UnderCover brand, light and dark. The queue with a count per state; each claim in full with its policy, claim history, the agent's decision and reasons, the wording of the policy section, and its steps live while it works (Run agent starts it); sign-off and payment for payouts over $1,000; and the agent's instructions read only. Views are hash links: `#/`, `#/claims/<id>`, `#/instructions`.
- `e2e/`: Playwright tests of the queue, a decision, the sign-off and the instructions. They run their own backend on port 8001 with a fresh database (`e2e/e2e.db`) and the dashboard on port 5174, and play the agent's part through the API, so they never call a model.

Not built, as the spec says: the claims manual, sign-in, real payments and messages to customers. There is no tool yet for scoring the agent against `data/evals/`.

## Running it

- `uv sync` and `npm install` once
- `npm run seed` rebuilds the database at `backend/undercover.db` (or the path in `UNDERCOVER_DB`). The backend seeds it on startup if it is missing. Run it again to put every claim back to waiting.
- `npm run dev` starts the backend on port 8000 and the dashboard on http://localhost:5173
- Open a claim and press Run agent, or run `uv run -m agent CLM-1001` with the backend running. The agent uses `openai/gpt-6-luna` on OpenRouter, or the model in `MODEL_NAME`, such as `openrouter/free`.
- `npm run check` runs every check
