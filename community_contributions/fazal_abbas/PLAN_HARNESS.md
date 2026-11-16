# Plan: the agent's harness

Built from `docs/HARNESS.md`, within `docs/TECH_STACK.md`, `docs/CODE_STANDARDS.md`, `docs/PROCESS.md` and `docs/BRAND.md`. This plan writes no code; implementation starts when asked. `docs/PLAN.md` is the pilot's finished plan and stays as it is.

## What we're building

The pilot's code organizes the work: it feeds the agent one claim at a time and hands it the whole policy wording. This build moves that organizing into the agent, and gives it the claims manual to read.

- **The queue runner**, an agent that works a whole queue in one run. It reads its to-do list, chooses the order, hands each claim to a worker, keeps the list up to date, and ends with a short summary for the handlers.
- **The claim worker**, an agent that works one claim from a clean start and reports back in a line: the decision and payout, or what went wrong.
- **The run and its to-do list**, held by the backend, so the dashboard can show the handlers what the agent means to do and how far it has got.
- **The documents, read by section.** The agent finds and reads the sections of the wording and the manual that a claim needs, and the claim page shows what it read.

## Decisions and why

**Two agents, one harness.** Both are LangChain's `create_agent`, as `docs/TECH_STACK.md` requires: the runner has the queue tools, the worker has the claim tools, and each has its own instructions. No second agent framework is added.

**The worker is a fresh run per claim.** `work_claim` starts the claim through the backend and waits for it, then returns one line. Because each claim is a new `create_agent` invocation with its own message history, the runner's context holds only a line per claim, so step 20 of a run costs about what step 1 cost. This is what `docs/HARNESS.md` asks for, and it is what stops a long run getting slower and dearer as it goes.

**The backend owns the run, the list and the rules.** The agent asks it to start a run, to move an item along, and to finish. Three things follow:

- The cap is exact. The backend takes the first *cap* waiting claims into the run and leaves the rest waiting, so a trial on five claims costs five claims' worth of model calls and no more. The agent chooses the order it works them in.
- The finish check cannot be skipped. `finish_queue_run` refuses (409) while any item is still to do, or is marked done on a claim with no decision, so a run cannot report itself finished with a claim left unworked.
- The rules of the pilot still hold whatever the model does: a decision is recorded once per claim, a claim is paid once, and a payout over $1,000 waits for a handler's sign-off.

**A failure is a first-class outcome, not an exception.** Every failure path ends in the same place: the claim goes back to waiting with the reason kept as a step, and its failure count goes up.

- A claim that fails before it is decided goes back in the queue, and the runner tries it once more in the same run.
- A claim that has failed twice is left for a handler: a new run does not take it, so it cannot burn model calls for ever. It stays in the queue as waiting and a handler can still run it by hand from its claim page.
- One bad claim never stops the run: `work_claim` returns the failure as a line, and the runner carries on with the next item.
- The provider's own errors are already handled: the model client retries a rate-limited call for about a minute, and a hard error comes back as a failed claim.
- A claim agent that runs too long is stopped. The worker runs under a wall-clock limit (`CLAIM_TIMEOUT_SECONDS`, 120 by default), and when it is passed the run is finished with the timeout as the note, which returns the claim to waiting. The abandoned call may still be running, but its later writes are refused by the backend, because the claim is no longer in progress.
- A claim left in progress by an interrupted run is put back to waiting, with a step, when the next run starts.

**The documents are served by section.** `backend/documents.py` splits a document on its `## N. Title` headings, and the sections are served by number. The worker lists the sections, reads the ones the claim needs and never receives a whole document. Each read is a step carrying the section's title, so the claim page shows what the agent read. The manual is loaded by the seed from `data/claims_manual.md`, and `docs/SPEC.md` is updated, where it is still "Not for now".

**Two sets of instructions.** `backend/instructions_queue.md` and `backend/instructions_claim.md`, served by `GET /api/instructions/queue` and `GET /api/instructions/claim`, and shown read only on the instructions page. Both are written from the wording and the manual. Neither is written from the handlers' decisions in `data/evals/`, which this build does not open.

**The model.** `deepseek/deepseek-v4.1-flash` at low reasoning effort becomes the default, as the brief asks. `MODEL_NAME` still overrides it, and `MODEL_NAME=openrouter/free` still runs the whole thing for nothing.

**Where the code goes.**

- `backend/documents.py`: splitting a document into sections.
- `backend/runs.py`: the run endpoints, in their own `APIRouter`; `backend/main.py` includes it, so the operation-shape test covers them.
- `backend/db.py`: the two new tables, the failure count and the small migration that adds them.
- `agent/client.py`: the backend client, moved out of `agent/main.py` so the tools can use it.
- `agent/tools.py`: the claim tools, the queue tools and the step recorder.
- `agent/main.py`: `run_claim`, `run_queue` and `model()`.
- `agent/__main__.py`: the command line.

## Phase 1: The documents and the instructions

- `backend/documents.py`: `read_document(text)`, giving the preamble and a list of `{section, title, text}` split on `## ` headings. The section id is the number in the heading, such as `6`.
- The seed loads `data/claims_manual.md` as the setting `claims_manual`, and `backend/db.py` stops loading the wording into the database by name only; the wording is already a setting.
- Operations, replacing `get_policy_wording` and `get_instructions`:
  - `list_wording_sections`: `GET /api/policy-wording/sections`, each with its number and title
  - `get_wording_section`: `GET /api/policy-wording/{section}`
  - `list_manual_sections`: `GET /api/manual/sections`
  - `get_manual_section`: `GET /api/manual/{section}`
  - `get_queue_instructions`: `GET /api/instructions/queue`
  - `get_claim_instructions`: `GET /api/instructions/claim`
- `backend/instructions_queue.md`: the runner's instructions. The to-do list and how to keep it up to date, choosing the order, handing each claim to a worker, trying a failed claim once more, leaving a claim that failed twice for a handler, and finishing with a short summary.
- `backend/instructions_claim.md`: the pilot's instructions, extended for the manual and the section tools. It covers the order the manual works a claim in, the interpretation notes that bind decisions (unattended belongings, vehicles, pairs and sets, wild animals, waiting periods, delay on the way home, reasonable accommodation, consequential losses, the value of information, adventure sports, pre-existing conditions, treatment that can wait), the repeat-claim rule, meals without receipts, documents and when to refer, and the rule that the story and the documents are evidence and never instructions.
- `docs/SPEC.md`: the manual moves out of "Not for now" and into the rules that decisions follow.

Success criteria:

- [x] `uv run pytest` passes new tests in `backend/tests/test_documents.py`:
  - the manual splits into 14 sections, numbered 1 to 14, and the wording into 12
  - the manual's section 6 is titled "Working out the payout" and the wording's section 5 is "Baggage and Personal Effects"
  - the preamble and every section's text, joined in order, give the file's text exactly
  - a document with no `## ` headings gives one empty section list and the whole text as the preamble
- [x] Tests on the reads: `GET /api/manual/sections` lists 14 sections with titles, `GET /api/manual/6` returns the manual's section 6, `GET /api/policy-wording/sections` lists 12, `GET /api/policy-wording/5` returns the wording's section 5, and an unknown section on either returns 404.
- [x] A test: `GET /api/policy-wording` and `GET /api/instructions` are gone, both returning 404.
- [x] A test: the seed reads exactly the eight named files, and the text served by `GET /api/manual/9` is in `data/claims_manual.md`.
- [x] A test: `GET /api/instructions/queue` and `GET /api/instructions/claim` return the text of their files, the claim instructions name the manual, and neither mentions `data/evals`.
- [x] The existing test over `app.routes` passes with the larger set: every operation has an `operation_id`, a one-line docstring and no optional inputs.
- [x] `npm run check:python` passes.

## Phase 2: The run and its to-do list

- `backend/db.py`: `runs` and `run_items` tables, and a `failures` count on `claims`. A database made by the pilot build gains them the next time it is opened, with its decisions intact.
- `backend/runs.py`:
  - `start_run`: `POST /api/runs` with a cap, returning 202. It puts back to waiting any claim left in progress by an interrupted run, takes the lowest-numbered waiting claims that have failed fewer than twice, up to the cap, makes one `to_do` item for each, and starts the runner in the background. A run while one is in progress returns 409.
  - `get_current_run`: `GET /api/runs/current`, the most recent run with its items, its cap, when it started and its summary, or `null` before the first run.
  - `set_run_item`: `POST /api/runs/{run_id}/items/{claim_id}`, the item's state and a note. The states are `to_do`, `in_progress`, `done` and `left_for_handler`.
  - `finish_queue_run`: `POST /api/runs/{run_id}/finish`, the summary. It returns 409, naming the items, while any item is `to_do` or `in_progress`, or is `done` on a claim with no decision.
- `finish_run` on a claim (the existing operation) counts a failure when it ends with no decision.
- `list_claims` and `get_claim` carry the failure count.

Success criteria:

- [x] A test: a database seeded with the pilot's schema opens, gains the new tables and the column, and keeps a decision it already held.
- [x] Tests on the cap: `POST /api/runs` with a cap of 5 makes a run of `CLM-1001` to `CLM-1005`, all `to_do`, leaves the other 20 waiting, and returns 202.
- [x] A test: a second run while one is in progress returns 409.
- [x] A test: a claim left in progress by an interrupted run goes back to waiting, with a step, when the next run starts.
- [x] Tests: `set_run_item` sets each of the four states; an unknown state returns 422; a claim that is not in the run returns 404.
- [x] Tests on the finish check: 409 naming the items while one is still `to_do`; 409 while one is `done` on a claim with no decision; 200 with the summary once every item is `done` or `left_for_handler`.
- [x] Tests on failures: `finish_run` with no decision raises the claim's failure count and returns it to waiting; a claim that has failed twice is not taken into a new run; `list_claims` shows the count.
- [x] `npm run check:python` passes.

## Phase 3: The claim worker

- `agent/tools.py`: the claim tools become `get_claim`, `list_wording_sections`, `get_wording_section`, `list_manual_sections`, `get_manual_section`, `record_decision` and `pay_claim`. No tool returns the whole wording or the whole manual.
- A section read records its own step, with the section's title as the detail, so the claim page shows what the agent read. The step recorder skips it, so a read is one step and not two.
- `agent/main.py`: `run_claim(claim_id, thread_id)`, the pilot's `run` under a wall-clock limit of `CLAIM_TIMEOUT_SECONDS` (120 by default). The model's answer, an error and a timeout all end in `finish_run`, so the claim is never left in progress.
- `model()`: `deepseek/deepseek-v4.1-flash` at low reasoning effort by default, or `MODEL_NAME` if set.

Success criteria:

- [x] A stub test: a claim's steps are `started`, `get_claim`, the sections it read, `record_decision`, `pay_claim`, `finished`, and the read steps carry the section titles.
- [x] A test: the claim agent's system prompt is the text of `GET /api/instructions/claim`.
- [x] A test: no tool's reply is the whole wording or the whole manual.
- [x] A test: a model that takes longer than `CLAIM_TIMEOUT_SECONDS` (0.2 in the test) leaves the claim waiting with a step naming the timeout, and the claim's failure count is 1.
- [x] A test: the claim agent that fails twice leaves the claim waiting with a failure count of 2, and a new run does not take it.
- [x] The existing tests still pass, updated for the new tools: an approve and payment, an approval over the limit refused, a decline, a refer, and a model that raises.
- [x] A test: the default model is `deepseek/deepseek-v4.1-flash` at low reasoning effort, and `MODEL_NAME=openrouter/free` overrides it with no reasoning effort.
- [x] `npm run check:python` passes.

## Phase 4: The queue runner and the command line

- `agent/tools.py`: the queue tools, `get_run`, `work_claim`, `set_run_item` and `finish_queue_run`. `work_claim` starts the claim through the backend and waits for it to finish, then returns one line: the decision and payout, or the failure.
- `agent/main.py`: `run_queue(run_id)`, which invokes the runner with the queue instructions and the run id, and always ends by finishing the run.
- `agent/__main__.py`:
  - `uv run -m agent` starts a run over every waiting claim
  - `uv run -m agent --cap 5` starts a run capped at five
  - `uv run -m agent CLM-1001` still runs the agent on one claim and prints its steps
  - a run prints each item as it changes state, then the summary

Success criteria:

- [x] A stub test: a run of three claims works them in the order the model chooses, sets each item `done`, and ends with a summary; each claim holds its own steps, and the run is finished.
- [x] A stub test: a claim whose model fails once is worked again and succeeds; a claim that fails twice is marked `left_for_handler` and the run still finishes.
- [x] A stub test: a claim that fails does not stop the run, and the other claims are still decided.
- [x] A stub test: the runner cannot finish while an item is `to_do` (409), and finishing once every item is done works.
- [x] A test: the runner's system prompt is the text of `GET /api/instructions/queue`.
- [x] A test: a claim decided or paid twice is refused, and the refusal does not stop the run.
- [x] Tests on the command line: `uv run -m agent --cap 5` starts a capped run, prints each item and the summary, and `uv run -m agent CLM-1001` still runs one claim.
- [x] `npm run check:python` passes.

## Phase 5: The dashboard

- Queue page:
  - a Run the queue panel: a cap field, five by default, and a Start run button calling `start_run`, disabled while a run is in progress
  - the current run's to-do list, polled every two seconds: each claim with its state as To do, In progress, Done or Left for a handler, the run's cap and how far it has got, and the summary once the run has finished
  - a claim that has failed twice is marked in the row, so a handler can see it needs them
- Claim page: the sections the agent read, with their titles, in the steps.
- Instructions page: both documents, each under its own heading, read only.
- `dashboard/src/api.ts` gains the run and section calls, in strict types with no `any`.

Success criteria:

- [x] vitest tests with a stubbed `fetch`: the run panel starts a run with the cap typed in and is disabled while a run is in progress; the to-do list renders every item with its state; the summary shows once the run has finished; a claim that failed twice is marked; the read steps show the section titles; the instructions page shows both documents and has no input, textarea or contenteditable.
- [x] In the browser against `npm run e2e:serve`: starting a run capped at five shows the to-do list filling in and being ticked off, and the summary at the end.
- [x] In the browser against `npm run e2e:serve`: a claim's steps include the sections the agent read, named as the manual names them.
- [x] `npm run check:ts` passes with coverage of 80% or more.

## Phase 6: End-to-end tests, the documents and the full check

- `agent/tests/e2e_server.py`: the scripted model answers for both agents, telling them apart by their instructions, so a run can be started and followed without a real model.
- `e2e/`: a test that starts a run capped at five from the queue page, watches the to-do list fill in and tick off, sees the summary, and finds the other 20 claims still waiting; the existing tests for one claim, the sign-off and the instructions page are kept.
- `docs/SPEC.md`: the manual is part of every decision, the agent works the queue in one run with a to-do list, and the team sees that list.
- `docs/TECH_STACK.md`: the two agents and their tools, the section endpoints, and the default model.
- `docs/STATUS.md`: the product as it now is, with how to start a run, cap it, and read the to-do list.

Success criteria:

- [x] `npm run e2e` passes, with `npm run dev` running at the same time.
- [x] A test in `e2e/`: a run capped at five leaves the other 20 claims waiting, and the run's to-do list and summary are on the queue page.
- [x] `docs/SPEC.md` no longer says the manual is "Not for now", and describes the run, the to-do list and the summary.
- [x] `docs/TECH_STACK.md` and `docs/STATUS.md` describe the product as it now is.
- [x] `npm run check` passes in full: ruff, pyright, pytest at 80% or more, Prettier, ESLint, tsc, vitest at 80% or more and Playwright. No threshold lowered, rule turned off or file excluded.
- [x] A live run, with `OPENROUTER_API_KEY` in `.env`: `uv run -m backend.reset`, then a run capped at five on `deepseek/deepseek-v4.1-flash`. I report the decisions, anything left for a handler, the steps on one claim, and the cost from OpenRouter's dashboard. A capped run of five costs a few cents.
- Result of the live run: five claims worked on its own in about two minutes. CLM-1001 $420.00, CLM-1002 $580.00, CLM-1004 $186.00 and CLM-1005 $243.00 decided and paid; CLM-1003 approved for $3,750.00 and awaiting a handler's sign-off; the other 20 claims left waiting. The cost was $0.0252. CLM-1002's steps show the four sections of the wording and the six sections of the manual it read, and no whole document. Found while checking: the model wrote markdown in its closing note, which the handlers see as typed, so the claim instructions now ask for plain text.

## How I'll work

- I build the phases in order. For each one I check every criterion, tick it off here, update `docs/STATUS.md` and commit, with the pre-commit hook, never `--no-verify`.
- Tests never call a model. The stub model covers every new behavior the brief lists: the to-do list stored and shown, the cap, a failed claim that does not stop the run, a failed claim going back in the queue and being tried again, a claim that fails twice left for a handler, and the finish check.
- Nothing is pushed.
- Every script works on Windows, as `uv run` commands or `.mjs` files.

## Defaults I chose, which you can change

- **Who picks the claims.** The backend takes the lowest-numbered waiting claims into a capped run, so the cap is exact and the trial's cost is known before it starts. The agent chooses the order it works them in. If you would rather the agent chose which claims to take as well, the cap becomes a limit the agent is trusted to keep to.
- **A claim that has failed twice** stays in the queue as waiting, marked, and a handler can still run it by hand from its claim page. A separate "needs a handler" status would be clearer on the screen but would change the four statuses the spec defines.
- **One run at a time.** Starting a run while one is in progress returns 409, so two runs cannot fight over the same claims.
- **The timeout.** 120 seconds per claim, in `CLAIM_TIMEOUT_SECONDS`. The brief asks for timeouts to be handled; if you would rather not cut a slow claim off, the limit can go up or the claim can be left to the provider's own timeouts.
- **Section numbers as ids.** A section is addressed by the number in its heading, such as `/api/manual/6`, which is how a handler refers to it.
- **The runner waits for the worker.** `work_claim` waits for the claim to finish before returning its line, so there is one path for running the agent on a claim, shared with the Run agent button and `uv run -m agent CLM-1001`.

## What changes from the pilot

- `GET /api/policy-wording` and `GET /api/instructions` are replaced by the section reads and the two instruction documents. The agent never receives a whole document again.
- `uv run -m agent` starts one run over the queue, instead of looping over the claims itself.
- The default model becomes `deepseek/deepseek-v4.1-flash`.
- `claims_manual.md` is loaded by the seed, which the pilot's tests assert it is not.
