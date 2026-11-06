# Status

The pilot from `docs/PLAN.md` and the harness from `docs/PLAN_HARNESS.md` are built: a backend, the UnderCover Agent and a dashboard for the handlers. One run of the agent works the queue: a queue agent keeps a to-do list and hands each claim to a claim agent with a fresh start, which looks up the policy wording and the claims manual section by section. The harness around them retries failures, puts a failed claim back in the queue and leaves it for a handler after a second failure.

- `backend/`: FastAPI on SQLite. The database is `backend/undercover.db`, or the path in `UNDERCOVER_DB`. The backend seeds it from `data/` when it starts without one, and never reads `data/evals/` or `data/security/`.
  - Read operations: `list_claims`, `get_claim`, `get_policy` (with the plan's limits and add-ons), `get_customer`, `list_handlers`, `get_policy_wording`, `list_sections`, `search_documents`, `read_section`, `get_instructions`, `list_steps`, `get_latest_run` and `health`. The workflow: `start_claim`, `add_step`, `record_decision`, `pay_claim`, `release_claim` and `sign_off`. Runs: `start_run`, `update_todos` and `finish_run`.
  - A claim is `waiting`, `in_progress`, `waiting_for_sign_off`, `decided` or `left_for_handler`. A decline or referral is decided at once. An approval of $1,000 or less stays in progress until the agent pays it, and an approval over $1,000 waits for sign-off.
  - `release_claim` puts a claim back after a failed attempt and counts it in `attempts`. With no decision it goes back to `waiting`, and at its second failure to `left_for_handler`. An approval that wasn't paid goes to `left_for_handler` at once, since its decision is final.
  - `pay_claim` pays only an approved claim's exact payout, once, never on a claim left for a handler, and refuses a payout over $1,000 with `403`, whatever the agent does. A handler's `sign_off` pays those.
  - `backend/documents.py` splits the policy wording (12 sections) and the claims manual (14) at their numbered headings. `search_documents` is a keyword search that returns the five best sections with their best-matching lines, with rare words counting most.
  - A run is one start of the agent on the queue, with its to-do list (each item `to_do`, `in_progress`, `done` or `left_for_handler`), its summary, and when it started and finished. A finished run can't change.
  - The agent's instructions are `backend/instructions/queue.md` and `backend/instructions/claim.md`, served together by `get_instructions`.
- `agent/`: the UnderCover Agent, as two agents on LangChain's `create_agent` with DeepSeek V4.1 Flash at low reasoning through OpenRouter, or the model in `MODEL_NAME`.
  - `agent/common.py` holds the backend client, the model and the harness: LangChain's middleware retries a failed model call or backend call three times and stops an agent that makes too many model calls, and our `FinishCheck` middleware sends an agent back, at most twice, if it tries to finish with work undone. The claim agent is reminded if the claim is undecided or an approval of $1,000 or less is unpaid, and stopped after 25 model calls.
  - `queue_agent.run(cap, claim_ids)` starts a run and gives the queue agent three tools: `list_waiting_claims` (no customer names), `write_todos` (saves the whole to-do list on the run) and `work_claim`. `work_claim` refuses a claim outside the claims named or past the cap (which counts claims, not attempts), works one claim at a time, and prints each claim's line. Before the queue agent finishes, `FinishCheck` reminds it of any waiting claim it could still work, including one waiting for its second try. The run ends with the agent's summary, or "The run stopped: ..." if the queue agent itself fails. Its model call limit is 10, plus 4 for each claim the run may work.
  - `work_claim` calls `claim_agent.start`, then `claim_agent.attempt`, which runs the claim agent once (`run`) in a fresh context, posting each step to the backend, then reads the claim back. A finished claim gives a line such as "CLM-1001: approved $420.00 and paid." A claim left unfinished, by an error or otherwise, gets a failure step and is released, and the line says what went wrong.
  - Its tools each call one API operation: `get_claim`, `get_policy`, `get_customer` (name, customer since and earlier claims only, so no personal details reach the model), `list_sections`, `search_documents` and `read_section` (it looks up the wording and the manual instead of reading them whole), `record_decision` and `pay_claim`. A refusal from the backend goes back to the model as the tool's result.
- `dashboard/`: React, Vite and TypeScript in the UnderCover brand, with light and dark mode following the system setting. Routing is by the URL's hash, and the dev server proxies `/api` to the backend in `BACKEND_URL`, by default port 8000.
  - The queue (`#/`) counts the claims in each of the five statuses, shows the agent's latest run (running or finished, its to-do list with each item's status, and its summary), and lists every claim, refreshing every 2 seconds.
  - A claim (`#/claims/CLM-1001`) shows the agent's decision, reason, the section it relied on and the payment, or where the claim stands after a failed attempt. Then the claim with its items and documents, the agent's steps as they happen (with what it read listed first, refusals, reminders and failures marked, and each attempt numbered when there's more than one), the policy, and the customer with their earlier claims. A claim waiting for sign-off has a form to choose a handler and sign off, which pays it.
  - The agent's instructions (`#/instructions`) for running the queue and for working a claim, read only.
- `e2e/`: Playwright tests of the queue, the agent's run and its to-do list, a claim page, live steps, what the agent read, a claim left for a handler, sign-off and the instructions. They start their own backend on port 8001, freshly seeded into a database in the system's temp folder, and their own dashboard on port 5174, so they never touch the queue in `npm run dev`.

## Running it

### Start

From the root of the repo, run:

```
npm run dev
```

This starts the backend on port 8000 and the dashboard at http://localhost:5173. Leave that terminal open while you use them.

### Stop

Press Ctrl+C in the terminal where `npm run dev` is running.

If the servers were started somewhere else, for example by your coding agent, stop whatever is listening on the two ports:

- Mac or Linux: `lsof -ti tcp:8000,5173 | xargs kill`
- Windows PowerShell: `Get-NetTCPConnection -LocalPort 8000,5173 -State Listen | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force }`

The queue is saved in `backend/undercover.db`, so stopping loses nothing. A database from the pilot is missing the harness's tables and columns, so run `uv run -m backend.seed` once after updating.

### Other commands

- `uv run -m agent` starts one run of the queue agent on every waiting claim. It prints a line for each claim as it's worked, then the summary. `uv run -m agent --cap 5` works at most five claims, a cheap trial, and `uv run -m agent CLM-1001 CLM-1004` works just those claims. The backend must be running, so use a second terminal. This calls the model and spends on your OpenRouter key.
- `uv run -m backend.seed` resets the queue to the records in `data/` and clears the runs. A decided claim is final, so run this to work the queue again.
- `npm run check` runs every check. Its end-to-end tests start their own servers on other ports, so it's safe to run while `npm run dev` is up.

## Not built yet

What's left out is listed at the end of `docs/PLAN.md` and `docs/PLAN_HARNESS.md`: sign-in, real payments, messages to customers, scoring against `data/evals/`, working claims in parallel, screens for a handler to work a referred claim or one left for a handler, and a button that starts a run. Stopping a run with Ctrl+C partway through a claim leaves that claim in progress, so reseed to start again.
