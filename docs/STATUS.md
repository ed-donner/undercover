# Status

The claims pilot is built to `docs/PLAN.md`, every success criterion is ticked, and `npm run check` passes.

## Harness build (in progress, `docs/PLAN_HARNESS.md`)

- Phase 1 done: the backend serves the wording and the manual by section (`list_sections`, `read_section`), and `get_instructions` returns the queue agent's and the claim agent's instructions (`backend/instructions/`).
- Phase 2 done: runs with a to-do list and a cap (`start_run`, `write_todos`, `take_claim`, `list_missed_claims`, `finish_run`), `fail_claim` (back in the queue, then Needs a handler on the second failure), a strict `start_claim` and a sweep at startup. The dashboard does not show these yet.
- Phase 3 done: the claim agent (`agent/claim_agent.py`, shared parts in `agent/harness.py`) has seven tools including `list_sections` and `read_section`, records a `read` step for each section it reads, retries model and tool calls, and `work` leaves every claim in a good state when a run fails. The default model is `deepseek/deepseek-v4.1-flash`. `uv run -m agent.main CLM-1001` runs one claim.
- Phase 4 done: the queue agent (`agent/queue_agent.py`) with `list_waiting_claims`, `write_todos`, `work_claim` and `check_queue`, a hook that sends it back to work if it tries to finish with claims it could still take, and `run_queue` taking a `limit`. `uv run -m agent.main queue --limit 5` runs it from the command line.
- Phase 5 done: the queue page shows the current run and its to-do list, a trial box and the Needs a handler status; the claim page lists what the agent read; the instructions page shows both texts.

## What is built

- `backend/`: FastAPI and SQLite, seeded from `data/` on first start (never from `data/evals/`). It serves claims, policies, customer history (no contact details), the policy wording, the agent's instructions and the handlers. It runs the claim workflow: start, decision, payment, sign-off and steps. `pay_claim` refuses with a 409 unless the claim has an approved decision, the amount equals the payout, it is unpaid and, over $1,000, a handler has signed off. A sign-off records the payment. `run_claim` and `run_queue` start the agent in the background.
- `agent/`: `create_agent` on OpenRouter with six tools over the backend's API. It fetches its instructions from the backend, starts the claim, and records each tool call, result and message as a step. `uv run -m agent.main CLM-1001` runs it on one claim. Tests use a stub model.
- `dashboard/`: the queue (status counts, filter, run buttons), the claim screen (the claim, the decision and its reasons, the agent's steps, the policy, the customer's history and the sign-off panel) and the read-only instructions. Light and dark, in the brand colors and fonts.
- `e2e/`: Playwright tests on their own ports (8100 and 5273) and a throwaway database. They stand in for the agent through the API.
- `backend/instructions.md`: the agent's instructions, shown in the dashboard.

## Live run

Run once against `openai/gpt-6-luna` on 2026-10-18, with a fresh queue:

- CLM-1001 (trip delay): approved, $420.00 paid. The decision, section and steps were recorded. Its explanation contained a made-up "p.m." for the departure time.
- CLM-1003 (emergency medical, $3,800 claimed): approved for $3,750.00 (less the $50 deductible), left waiting for sign-off, no payment made, and the agent did not try to pay.
- On both, the model called `get_customer` with a wrong id, got a 404 and carried on. On CLM-1003 it never read the customer's history, which its instructions require.

## Run it

- `uv sync` and `npm install` once.
- `npm run dev` starts the backend on port 8000 and the dashboard at http://localhost:5173.
- `npm run check` runs every check.
- The database is `backend/undercover.db`. Delete it to reset the queue.

## Notes

- The agent's payout arithmetic is its own. Nothing checks it, and accuracy against the handlers' decisions has not been measured.
- A claim whose agent run fails stays In progress, with an error step. Running the agent on it again is allowed from the command line; the dashboard's Run agent button is for waiting claims only.
