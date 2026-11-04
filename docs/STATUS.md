# Status

Built so far: the claims platform for the pilot and the harness work (docs/PLAN_HARNESS.md).

- `backend/`: SQLite database and API for claims, policies, customers, the claims manual and policy wording by section, steps, decisions, payments, sign-off (payments over $1,000 blocked until signed off), runs with to-do lists, and failures. Claim statuses: waiting, in progress, awaiting sign-off, decided, left for handler. A failed claim returns to waiting; on the second failure it is left for a handler.
- `agent/`: the queue runner and the per-claim subagent. A run can be capped (`--limit N`) or on one named claim (`--claim CLM-1001`). The runner checks for missed waiting claims before it finishes. Default model `deepseek/deepseek-v4.1-flash`, low reasoning effort; `MODEL_NAME` overrides it.
- `dashboard/`: the queue page (statuses, current run's summary and to-do list), the claim page (decision, steps, sections read) and the instructions page.
- `e2e/`: Playwright tests of the pages against a seeded test database.

## How to run it

- `uv sync` and `npm install` once. Put `OPENROUTER_API_KEY` in `.env`.
- `npm run seed` resets the database to 25 waiting claims. Run it before every agent run.
- `npm run dev` starts the backend (port 8000) and the dashboard (port 5173).
- `npm run run -- --limit 5` runs the agent on at most 5 claims; `npm run run -- --claim CLM-1001` runs it on one claim. The backend must be running.
- `npm run check` runs every check: ruff, pyright, pytest, Prettier, ESLint, tsc, vitest and Playwright. No test calls a model.

## Live check

After 
pm run seed, 
pm run run -- --limit 5 on the default model worked exactly 5 claims on its own (2 approved and paid, 1 declined, 2 referred), left the other 20 waiting, left none in progress, and decided and paid nothing twice. Each worked claim shows its steps and the sections it read. A first attempt hit an OpenRouter credit limit (402) because the model asked for up to 131,072 output tokens; the run survived it, and gent/model.py now caps the output at 8,000 tokens.
