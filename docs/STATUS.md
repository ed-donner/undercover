# Status

The pilot from `docs/SPEC.md` is built, per the plan in `docs/PLAN.md`.

- `backend/`: FastAPI and an in-memory SQLite database, reseeded from `data/` (never `data/evals/`) every time the backend starts.
  - `db.py`: the schema, the seeding, and every query. All of it - reads and writes - goes through one lock, since a bare SQLite connection isn't safe for the concurrent requests a page load fires at once.
  - `claims.py`: the claim lifecycle - `run_claim`, `decide_claim`, `pay_claim`, `sign_off_claim` - and the $1,000 sign-off rule, enforced in `pay_claim` wherever the payment comes from.
  - `agent_instructions.md`: the agent's instructions, served read-only and used as its own system prompt, so the two can never drift apart.
  - `main.py`: the API - `list_claims`, `get_claim`, `get_policy_wording`, `list_handlers`, `list_claim_events`, `run_claim`, `decide_claim`, `pay_claim`, `sign_off_claim`, `get_agent_instructions`, plus the original `health`.
- `agent/`: the UnderCover Agent. `run(claim_id, thread_id)` reads a claim, the customer's policy and claim history, and the policy wording, then decides approve/decline/refer and tries to pay - all through the backend's API, never touching `data/` directly.
- `dashboard/`: React, Vite, TypeScript, React Router, styled to `docs/BRAND.md`.
  - **Queue** (`/`) - every claim, with a Run button on each waiting one, polling live while any claim is in progress.
  - **Claim detail** (`/claims/:id`) - the story, items, documents, customer, policy, the decision once made, the step-by-step event log, and a sign-off control when a claim needs one.
  - **Instructions** (`/instructions`) - the agent's instructions, rendered from the same Markdown the agent reads.
- `e2e/`: Playwright tests for the queue, a claim's detail page and the sign-off flow, seeded through the backend's own API rather than a model.

Everything in `docs/SPEC.md` is built: the queue view, a claim in full with its decision and reasons, the step-by-step trace, read-only instructions, the $1,000 sign-off block, decisions grounded in the policy wording, and the "not for now" items (the claims manual, sign-in, real payments, customer messages) are genuinely absent.

## Running it

`npm run dev` starts the backend (`http://localhost:8000`) and the dashboard (`http://localhost:5173`). `npm run check` runs every check: Python (ruff, pyright, pytest at 80%+ coverage), TypeScript (ESLint, Prettier, tsc, vitest at 80%+ coverage) and the Playwright end-to-end tests.
