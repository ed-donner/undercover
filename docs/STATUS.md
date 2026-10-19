# Status

The claims pilot is built to `docs/PLAN.md` and the agent's harness to `docs/PLAN_HARNESS.md`. Every success criterion in both is ticked and `npm run check` passes.

## What is built

- `backend/`: FastAPI and SQLite, seeded from `data/` on first start (never from `data/evals/`). It serves claims, policies, customer history (no contact details), the policy wording and the claims manual by section (`list_sections`, `read_section`), the two sets of agent instructions and the handlers. It runs the claim workflow: start (waiting claims only), decision, payment, sign-off, steps and `fail_claim`. `pay_claim` refuses with a 409 unless the claim has an approved decision, the amount equals the payout, it is unpaid and, over $1,000, a handler has signed off. A sign-off records the payment.
- Runs: `start_run` takes a cap, `take_claim` refuses a claim over the cap, `write_todos` stores the to-do list, `list_missed_claims` shows the waiting claims a run could still take and `finish_run` stores the summary. A claim that fails goes back to waiting; its second failure sets Needs a handler. One run runs at a time. When the backend starts it closes any open run and releases claims left in progress. `run_queue` (capped) and `run_claim` start the agents in the background.
- `agent/`: two agents on `create_agent`. The queue agent (`queue_agent.py`) has `list_waiting_claims`, `write_todos`, `work_claim` and `check_queue`; a hook sends it back to work if it tries to finish with claims it could still take. `work_claim` runs a claim agent (`claim_agent.py`), fresh for each claim, with `get_claim`, `get_policy`, `get_customer`, `list_sections`, `read_section`, `record_decision` and `pay_claim`. The entry point records every call, result and message as a step, and a `read` step for each section read. `work` puts the claim right if the claim agent fails: back in the queue, left for a handler on the second failure, and an approved payout of $1,000 or less that was left unpaid is paid. Model and tool calls are retried, and each agent has a call limit (`harness.py`). The default model is `deepseek/deepseek-v4.1-flash`; `MODEL_NAME` overrides it. Tests use a stub model.
- `dashboard/`: the queue (status counts, filter, the current run with its to-do list and summary, run buttons and a trial box), the claim screen (the claim, the decision and its reasons, what the agent read, the agent's steps, the policy, the customer's history and the sign-off panel) and the read-only instructions. Light and dark, in the brand colors and fonts.
- `e2e/`: Playwright tests on their own ports (8100 and 5273) and a throwaway database. They stand in for the agent through the API.
- `backend/instructions/`: `queue.md` and `claim.md`, shown on the instructions page. They were written from the policy wording and the manual, not from `data/evals/`.

## Live run

On 2026-10-19, on a fresh queue with the default model, a run capped at 5 claims took 2 minutes 40 seconds:

- The queue agent wrote a five-item to-do list, ticked each off as it went and finished with a summary. It chose CLM-1001, 1008, 1011, 1018 and 1010. 20 claims stayed waiting.
- CLM-1001 approved and paid $420.00. CLM-1008 ($2,240.00) and CLM-1011 ($1,150.00) approved and held for sign-off, with no payment made. CLM-1010 declined (the medical records show the tooth was lost while the customer was impaired by alcohol). CLM-1018 referred for a missing proof of value, as the manual says.
- No claim failed, so retries were not exercised live. No claim was left in progress, none was decided twice and only CLM-1001 was paid.
- The claim agent read 11 to 16 sections on every claim, nearly the whole manual each time, in 46 to 62 steps. That is thorough and slower than needed. It read the manual's section on repeat claims on all five.
- The queue agent's summary has Markdown in it (`check_queue` in backticks), and the to-do items show the raw claim type, such as `trip_delay`.
- Cost was not measured. Accuracy against the handlers' decisions has not been measured either.

## Run it

- `uv sync` and `npm install` once.
- `npm run dev` starts the backend on port 8000 and the dashboard at http://localhost:5173.
- `uv run -m agent.main queue --limit 5` runs the queue agent on at most 5 claims, and `uv run -m agent.main CLM-1001` works one waiting claim. The dashboard does the same with Run trial and Run agent. Without `--limit` a queue run takes every waiting claim.
- `npm run check` runs every check.
- The database is `backend/undercover.db`. Delete it to reset the queue; the live run above is in it now.

## Notes

- The agent's payout arithmetic is its own. Nothing checks it, and accuracy against the handlers' decisions has not been measured.
- The queue agent's own steps are not recorded anywhere; the run shows its to-do list and summary. Claim agent steps are on each claim.
- A claim the agent fails on twice shows as Needs a handler. Nothing in the dashboard puts it back in the queue; delete the database to reset.
