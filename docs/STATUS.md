# Status

The claims pilot, built from `docs/PLAN.md`. Phases 1 to 5 of 6 are done.

- `backend/`: FastAPI and SQLite. The database (`backend/undercover.db`, or `UNDERCOVER_DB`) is seeded from `data/` on first start, leaving out `data/evals/`. Read operations: `list_claims`, `get_claim`, `get_policy`, `get_claim_history`, `get_policy_wording`, `get_instructions`, `list_handlers`. Write operations: `add_step`, `list_steps`, `record_decision`, `pay_claim`, `sign_off`. A payout over $1,000 waits for a handler's sign-off, and `pay_claim` refuses it until then. `run_agent` and `run_queue` start the agent in the background; a run that ends without a decision puts the claim back to waiting
- `agent/`: the UnderCover Agent, `run(claim_id, thread_id)`. Its tools call the backend (`get_claim`, `get_policy`, `get_claim_history`, `get_policy_wording`, `record_decision`, `pay_claim`), its instructions come from `backend/instructions.md` through `get_instructions`, and it records each step through `add_step`
- `dashboard/`: React, Vite and TypeScript in the UnderCover brand, light and dark. The queue (`#/`) with a count for each state and a Run the queue button, and the agent's instructions, read only (`#/instructions`). The claim page (`#/claims/<id>`) shows the claim, its policy, the decision with its reason and section, the payment, a Run agent button, the agent's steps as it works, and sign-off by a handler for payouts over $1,000
- `e2e/`: one test of that page

## Running it

- `npm run dev` starts the backend on port 8000 and the dashboard on port 5173
- `uv run -m backend.db --reset` rebuilds the database from `data/`
