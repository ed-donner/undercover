# Status

UnderCover with the pilot and the harness built (`docs/PLAN_HARNESS.md`):

- `backend/`: FastAPI and SQLite, seeded from `data/` (never `data/evals/`). Claims, decisions, payments with the $1,000 sign-off rule, runs with a cap and a to-do list, steps on every claim, retries (a claim that fails twice is left for a handler), the claims manual and policy wording by section, and the instructions in `backend/instructions/`.
- `agent/`: a queue agent that plans a to-do list, works claims in the order it chooses and hands each to a fresh claim agent, which looks up the manual and wording sections it needs. Failures go back to the backend (retry, then a handler), and the run checks for missed claims before it finishes. Default model `deepseek/deepseek-v4.1-flash`; `MODEL_NAME` overrides it.
- `dashboard/`: the queue with the current run's to-do list, the claim page (decision, steps, sections read, sign-off), and the instructions page.
- `e2e/`: Playwright tests of the to-do list, claim page, instructions and sign-off.

## Run

- `npm run dev` starts the backend and the dashboard (http://localhost:5173).
- `npm run reseed` resets the data. Always reseed before a live run.
- `npm run agent -- --limit 5` works at most five waiting claims. `npm run agent -- --claim CLM-1001` works one claim. With no flag it works the whole queue. Needs `OPENROUTER_API_KEY` in `.env`.
- `npm run check` runs every check. Tests never call a model.
