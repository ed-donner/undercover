# Plan: the agent's harness

Source: `docs/HARNESS.md`. Built to `docs/SPEC.md`, `docs/TECH_STACK.md`, `docs/CODE_STANDARDS.md`, `docs/PROCESS.md` and `docs/BRAND.md`, on the pilot described in `docs/STATUS.md`. `docs/PLAN.md` is the pilot's finished plan and stays as it is.

## What we are building

Today our code does the organizing: `run_waiting` feeds the agent one claim at a time, the agent is handed the whole policy wording, and a failed claim stays in progress. This build moves that work into the agent.

```
                      +-- list_waiting_claims
 queue agent ---------+-- write_todos   -> to-do list, shown on the queue page
 (one run, a cap)     +-- work_claim  --> claim agent (fresh each time, one claim)
                      +-- check_queue        |-- get_claim, get_policy, get_customer
                                             |-- list_sections, read_section (wording, manual)
                                             +-- record_decision, pay_claim
```

- **The queue agent** starts once, plans the run as a to-do list, picks the order, hands each claim to a claim agent and finishes with a short summary for the handlers.
- **The claim agent** is a fresh `create_agent` for each claim. It looks up the sections of the wording and the manual it needs, decides, records and pays. It reports back in one line, so the queue agent's context grows by a line per claim, not by a claim's worth of work.
- **Our code** keeps what must not depend on the model: the cap, the retry rules, the payment rule and the check for missed claims.

Both agents are our own `create_agent` with our own tools and the middleware that ships in LangChain 1.4 (`ModelRetryMiddleware`, `ToolRetryMiddleware`, `ModelCallLimitMiddleware`, and `after_model` for the missed-claims check). No new framework: `deepagents` is installed for the course but we do not use it.

## How a claim moves

One new status, for a claim a handler must take over.

| Status shown | Meaning | How it gets there |
|---|---|---|
| Waiting | In the queue, nobody has started | Seeded; or `fail_claim` after a first failure |
| In progress | A claim agent is working it | `start_claim` (waiting claims only) |
| Waiting for sign-off | Approved for more than $1,000, payment held | `record_decision` |
| Decided | Finished | `record_decision`, or `sign_off_claim` |
| Needs a handler | The agent failed on it twice | `fail_claim` on the second failure |

A to-do item is `todo`, `in_progress`, `done` or `left_for_handler`.

## The API

Every operation has an `operation_id`, a one-line docstring and no optional inputs. New and changed operations:

| Method and path | operation_id | What it does |
|---|---|---|
| GET `/api/documents/{document}/sections` | `list_sections` | Section numbers and titles of `wording` or `manual`; 404 for any other document |
| GET `/api/documents/{document}/sections/{number}` | `read_section` | One section's text, heading first; 404 if it does not exist |
| GET `/api/instructions` | `get_instructions` | Changed: returns the queue agent's and the claim agent's instructions |
| POST `/api/runs` | `start_run` | Takes `limit` (a whole number, at least 1) and starts a run record; 409 if a run is already running |
| GET `/api/runs/latest` | `get_latest_run` | The latest run: limit, status, summary and to-do list; null if there has been none (a 404 would show as an error in the browser console) |
| PUT `/api/runs/{run_id}/todos` | `write_todos` | Replaces the run's to-do list with the given items (text and status) |
| POST `/api/runs/{run_id}/claims/{claim_id}` | `take_claim` | Hands a waiting claim to the run; 409 if the claim is not waiting or the run has already taken `limit` different claims |
| GET `/api/runs/{run_id}/missed` | `list_missed_claims` | Waiting claims the run could still take within its cap; empty means nothing was missed |
| POST `/api/runs/{run_id}/finish` | `finish_run` | Takes the summary and a status (`finished` or `failed`) and closes the run |
| POST `/api/claims/{claim_id}/fail` | `fail_claim` | Takes a reason. On an in-progress claim: records an error step and a failure; back to waiting after the first, needs a handler after the second. 409 on any other status |
| POST `/api/queue/run` | `run_queue` | Changed: takes `limit`, calls `start_run` and runs the queue agent in the background; returns the run |
| POST `/api/claims/{claim_id}/run` | `run_claim` | Unchanged for the caller: runs one named waiting claim |

`start_claim` becomes strict: waiting claims only, 409 otherwise. A claim that fails no longer sits in progress for a retry; it goes back to waiting. `get_policy_wording` stays, since it is the backend's read of the document, but the agent no longer has a tool for it.

New tables: `runs`, `todos`, `run_claims` (which claims a run has taken) and `failures` (claim, reason, time). A claim's number of failures is the count of its rows, so no existing table changes and an existing database still works. New step kind: `read`.

## Decisions I made

Please change any you disagree with before I build.

- **"Left for a handler" is a new status, Needs a handler**, not a recorded refer. A refer is a decision about the claim; a claim the agent crashed on has no decision. It gets a Raspberry chip (the brand's alert color), a count on the queue page, and a line in `docs/SPEC.md`.
- **The cap counts different claims a run takes on.** A retry of a claim the run has already taken does not use up the cap. `run_queue` from the dashboard sends the number of waiting claims for "all" and a number for a trial, so `limit` is never optional. The command line is `uv run -m agent.main queue --limit 5` and `uv run -m agent.main CLM-1001` stays.
- **The cap, the retry rule and the missed-claims check live in the backend and the harness, not in the prompt.** `take_claim` refuses a claim over the cap, `fail_claim` decides waiting or needs a handler, and an `after_model` hook stops the queue agent from finishing while `list_missed_claims` is not empty: it adds a message naming the missed claims and sends the agent back to work. The agent also has a `check_queue` tool and its instructions tell it to call it. The hook is the backstop if it forgets, with at most three nudges.
- **Failures are handled by code around the claim agent**, in the `work_claim` tool. If the claim agent raises, or finishes with the claim still in progress (no decision recorded), the tool calls `fail_claim` and returns a line saying what went wrong and whether the claim is back in the queue or left for a handler. Nothing the model does can leave a claim in progress.
- **A decided claim is never reset.** If a claim agent fails after `record_decision` but before `pay_claim` on an approve of $1,000 or less, the tool pays it with the recorded payout, going through the same `pay_claim` check. A claim cannot be decided twice (the claim must be in progress, and there is one decision per claim) or paid twice (409).
- **The claim agent's report line is built from the backend's record**, such as "CLM-1001: approved $420.00, paid" or "CLM-1003: approved $3,750.00, waiting for sign-off", not from the model's last message. It cannot misquote the payout. The model's own final message is still recorded as a step on the claim.
- **A restart sweeps up.** When the backend starts, any run still marked running is marked failed and its in-progress claims go through `fail_claim`. Without this, `uvicorn --reload` in the middle of a run would leave claims stuck and block the next run.
- **One run at a time.** `start_run` returns 409 while a run is running, so two queue agents never race for the same claims.
- **Retries of model and tool calls use LangChain's middleware**, set to raise when they give up, so a model that stays down fails the claim, not the run. The model also gets a timeout. Exact settings are chosen in phase 3 after reading the installed middleware.
- **A call limit on each agent** (`ModelCallLimitMiddleware`) so a model that loops cannot burn the run. A claim agent that hits it has recorded nothing, so it counts as a failure.
- **Reads are recorded by the entry point, not by the model**, like the other steps. When `read_section` returns, the entry point adds a `read` step such as "Claims manual, 9. Repeat claims", taken from the result's heading line. The claim page lists them in a "What the agent read" panel, and the full timeline still shows every call.
- **The queue agent sees a short list, not claims.** `list_waiting_claims` returns each waiting claim's id, type, summary, amount claimed and date. The claim details stay with the claim agents.
- **The queue agent's own steps are not recorded on a claim**, since they belong to no claim. The run shows its to-do list, its status and its summary. Every claim agent step is on that claim, as today.
- **Instructions are two files**, `backend/instructions/queue.md` and `backend/instructions/claim.md`, and the instructions page shows both. I write them from `data/policy_wording.md` and `data/claims_manual.md`. I do not open `data/evals/`, and I do not copy the manual's rules into the prompt: the claim agent is told to look them up, with a short list of what to look for (third claim in 12 months, wild animals, meals without receipts, missing documents, disagreeing documents).
- **Model**: `deepseek/deepseek-v4.1-flash` with low reasoning effort is the default for both agents. `MODEL_NAME` overrides it and, as today, then sends no reasoning effort.
- **A dashboard trial control.** The queue page gets "Run agent on all waiting claims" and a number box (5 to start) with "Run trial". The brief asks for the cap on a run; the box makes it usable without the command line.
- **Reseeding** means deleting `backend/undercover.db`. The new tables are created when the backend starts, so an old database also works, but the brief's live run starts from a fresh one.

## Phase 1: Documents by section and two sets of instructions

Gives the agent something to look up and gives the instructions page its two texts. First, because the claim agent in phase 3 needs it and nothing here depends on a model.

- `backend/documents.py` splits `data/policy_wording.md` and `data/claims_manual.md` into sections at their `## N. Title` headings. Text before the first heading is section 0, "Introduction". `list_sections` and `read_section` serve them.
- Move `backend/instructions.md` to `backend/instructions/claim.md` (drafted here, finished in phase 3) and add `backend/instructions/queue.md` (a first draft, finished in phase 4). `get_instructions` returns both.
- Update the existing tests that read `/api/instructions` and the repository test that greps for `evals`.

Success criteria:

- [x] `uv run pytest -q backend` passes, with tests that use a temporary database and no network
- [x] `GET /api/documents/wording/sections` returns the 12 sections of the wording, and `manual` the 14 sections of the manual, each with a number and a title
- [x] `GET /api/documents/manual/sections/9` starts with "## 9. Repeat claims" and holds the sentence about a third claim in 12 months; `.../wording/sections/10` is "How we work out your payment"
- [x] An unknown document or section returns 404; the sections of the manual joined together contain the whole manual (a test checks that nothing is lost)
- [x] `GET /api/instructions` returns a queue text and a claim text; the OpenAPI document still shows an `operation_id` and a summary on every operation and no optional parameters
- [x] The test that greps `backend/` and `agent/` for `evals` still passes
- [x] Ruff, pyright and 80% coverage pass
- [x] Committed, with the pre-commit hook passing

## Phase 2: Runs, the to-do list, the cap and failures

Builds the rules in the backend and proves them by calling the API, before any agent uses them, as the pilot did with the payment rule.

- `runs`, `todos`, `run_claims` and `failures` tables, created with the others.
- The operations `start_run`, `get_latest_run`, `write_todos`, `take_claim`, `list_missed_claims`, `finish_run` and `fail_claim`.
- The `needs_handler` status in `Status` and the models; `start_claim` made strict.
- The startup sweep: it releases every claim left in progress, not only those of a run, since a restart stops all agents.
- `run_queue` takes `limit` in phase 4, together with the runner and the dashboard button that calls it, so the app works after every commit. The agent's `run` no longer starts the claim; its callers do.

Success criteria:

- [x] `uv run pytest -q backend` passes with a test for each rule below
- [x] `start_run` with a `limit` of 0 returns 422; a second `start_run` while one is running returns 409; after `finish_run` it is allowed
- [x] `write_todos` replaces the list, keeps the order given, accepts only the four statuses (a fifth returns 422), and `get_latest_run` returns it with the run's limit, status and summary
- [x] With a limit of 2, `take_claim` accepts CLM-1001 and CLM-1002 and refuses CLM-1003 with 409; taking CLM-1001 again after it went back to waiting is allowed
- [x] `take_claim` on an in-progress or decided claim returns 409
- [x] `list_missed_claims` shows the waiting claims the run could still take: all 25 at the start of a limit-5 run is capped to 5 names, and it is empty once 5 different claims have been taken and none of them is waiting
- [x] `fail_claim` on an in-progress claim records an error step with the reason and sets the status to waiting; a second `fail_claim` sets it to needs a handler; a third returns 409. On a waiting or decided claim it returns 409
- [x] `start_claim` on an in-progress claim returns 409; on a needs-a-handler claim returns 409
- [x] A claim with a decision cannot be given a second decision (409), and a paid claim cannot be paid again (409), re-checked after a `fail_claim` attempt on it
- [x] The startup sweep marks a leftover running run failed and puts its in-progress claims through `fail_claim` (a test creates the leftover state and starts the app)
- [x] The queue list and `ClaimSummary` accept the new status
- [x] Ruff, pyright and 80% coverage pass
- [x] Committed, with the pre-commit hook passing

## Phase 3: The claim agent

Rebuilds the pilot's agent as the claim agent: one claim, its own lookups, its own failure handling.

- `agent/claim_agent.py`: tools `get_claim`, `get_policy`, `get_customer`, `list_sections`, `read_section`, `record_decision`, `pay_claim` over the backend. The whole-wording tool is gone. The tools still return the backend's error text to the model.
- `claim_run(claim_id, thread_id, llm=None)`: fetches the claim instructions, runs a fresh `create_agent` with the retry and call-limit middleware, records every call, result and message as a step (and a `read` step for each `read_section`), and returns the final reply. It does not start the claim; the caller does. If it raises, it adds an error step and re-raises.
- `agent/harness.py` holds what both agents share: the backend client, the model (`DEFAULT_MODEL` becomes `deepseek/deepseek-v4.1-flash`, with a timeout and no client-side retries so the middleware owns them) and the middleware. `agent/main.py` is the command line.
- `backend/instructions/claim.md` finished: the manual's working order, what to look up, the three outcomes, the payout steps by section 10 of the wording, the explanation format, the $1,000 limit. At most about 60 lines.
- `work(claim_id, thread_id)` in `agent/claim_agent.py` runs `claim_run` and handles failure (`fail_claim`, the unpaid small approve, the one-line report). The backend's `run_claim` and the command line call it, and phase 4's `work_claim` tool will too, so a single named claim never stays stuck either.

Success criteria:

- [x] `uv run pytest -q` passes; tests use a scripted stub model and never call a model
- [x] The claim agent has exactly the seven tools above, and none reads `data/evals/` or the whole wording
- [x] A stub run that reads a manual section and a wording section, then decides and pays a small claim, ends with CLM-1001 decided, one payment, and a step for every call and result in order
- [x] That run leaves two `read` steps, such as "Claims manual, 9. Repeat claims", and `GET /api/claims/CLM-1001/steps` lists them
- [x] A stub run that tries to pay $1,250.00 gets the refusal back as a tool result, no payment exists, and the claim is waiting for sign-off
- [x] A stub model that raises leaves an error step and the exception propagates; with the retry middleware, a model that fails once and then answers still completes
- [x] `DEFAULT_MODEL` is `deepseek/deepseek-v4.1-flash` with low reasoning effort; `MODEL_NAME` overrides it and sends no reasoning effort
- [x] `backend/instructions/claim.md` is under about 60 lines, names the $1,000 limit, the three outcomes, the payout steps and the explanation format, tells the agent to use `list_sections` and `read_section`, and contains no figure taken from `data/evals/` (I never opened it)
- [x] Ruff, pyright and 80% coverage pass
- [x] Committed, with the pre-commit hook passing

## Phase 4: The queue agent

The agent that works the whole queue, with the to-do list, a claim agent per claim, retries and the check for missed claims.

- `agent/queue_agent.py`: tools (built for one run, so the model never passes a run id) `list_waiting_claims`, `write_todos`, `work_claim` and `check_queue`. `work_claim(claim_id)` calls `take_claim`, `start_claim`, `claim_run`, then checks the claim: decided or waiting for sign-off is a success; an exception or a claim still in progress goes to `fail_claim`; a decided, unpaid approve of $1,000 or less is paid. It returns the one-line report.
- `queue_run(run_id, limit, thread_id, llm=None, claim_llm=None)`: fetches the queue instructions, runs the queue agent with the retry and call-limit middleware and the missed-claims hook, then calls `finish_run` with the final reply. If the agent itself fails, it calls `finish_run` as `failed` and re-raises. No claim can be left in progress by that, since `work_claim` returns only after `work` has put its claim right.
- `backend/runner.py` replaces `run_waiting` (and `claim_next_waiting` goes): `run_queue` in the backend takes `limit`, starts the run and the background task calls `queue_run`. The dashboard's run-all button sends the number of waiting claims.
- Command line: `uv run -m agent.main queue --limit 5` (all waiting claims without `--limit`), which starts the run and prints the summary.
- `backend/instructions/queue.md` finished: plan the run as a to-do list first and keep it current (item states, and `left_for_handler` for a claim that failed twice), choose the order, work one claim at a time with `work_claim`, call `check_queue` before finishing, write a short summary for the handlers. About 40 lines.

Success criteria:

- [x] `uv run pytest -q` passes; tests use stub models for both agents and never call a model
- [x] The queue agent has exactly the four tools above
- [x] **Cap**: a stub run with `limit` 3 that tries to work five claims gets the refusal on the fourth as a tool result; exactly three claims are decided and 22 are still waiting
- [x] **To-do list**: a stub run that writes a list, ticks items off and finishes leaves the final list in `get_latest_run`, with the statuses the stub wrote
- [x] **One bad claim does not stop the run**: a stub where the claim agent raises on the first claim still decides the other claims in the run, the first claim shows an error step, and no claim is in progress at the end
- [x] **Back in the queue and tried again**: a claim whose first attempt raises goes to waiting, and when the stub works it again it is decided; the run's `run_claims` holds it once, so the cap is not used twice
- [x] **Failed twice**: a claim that raises on both attempts ends as needs a handler, has two failure rows, and is not offered by `list_waiting_claims` or `list_missed_claims`
- [x] A claim agent that finishes without recording a decision counts as a failure, not as done
- [x] **No double decision or payment**: a stub run that fails after `record_decision` leaves the claim decided, an approve of $1,000 or less is paid once by the tool, and a repeat of `work_claim` on it returns 409 and changes nothing
- [x] **Check for missed claims**: a stub that tries to finish with a waiting claim inside its cap is sent back to work by the hook and then works it; a stub with nothing missed finishes at once
- [x] A queue agent that raises ends the run as failed and leaves no claim in progress
- [x] `run_queue` in the backend (stub agents) returns 202 with the run, the background task finishes it, and a second call during a run returns 409
- [x] `backend/instructions/queue.md` tells the agent to plan a to-do list, to work claims through `work_claim`, to call `check_queue` before finishing, and to write a summary
- [x] Ruff, pyright and 80% coverage pass
- [x] Committed, with the pre-commit hook passing

## Phase 5: Dashboard

Shows the run, the new status and what the agent read. After the backend because it only draws what the API returns.

- **Types and API**: `Run`, `Todo`, the `needs_handler` status, the `read` step kind, the two instructions; `startRun`-style wrappers for `run_queue` with a limit and `get_latest_run`.
- **Queue page**: a "Current run" panel above the table with the run's status, its cap, the to-do list (each item with a chip: To do in Marigold, In progress in Cerulean, Done in Sea Green, Left for a handler in Raspberry) and, once finished, the agent's summary. Polled with the queue every 3 seconds. A number box and "Run trial" next to "Run agent on all waiting claims", which now sends the number of waiting claims. The status counts and filter get Needs a handler.
- **Claim page**: the steps timeline labels `read` steps "Read" and a "What the agent read" panel lists them (document and section). A claim that needs a handler says so.
- **Instructions page**: both texts, headed "Running the queue" and "Working a claim", read only.
- Plain US business English, brand colors, light and dark, no one-edge borders, no gradients. No new dependencies.

Success criteria:

- [x] `npm run check:ts` passes: Prettier, ESLint, tsc and vitest with 80% coverage
- [x] Vitest tests with a mocked `fetch` cover: the run panel with a list in each of the four item states, no panel before the first run, the summary on a finished run, the trial box sending its number, the run-all button sending the waiting count, the Needs a handler chip and count, the read panel, and the instructions page with both texts
- [x] With `npm run dev` and a run put in place with `curl` (`start_run`, `write_todos` with one item in each state), the Playwright MCP server shows the list on `http://localhost:5173/` in light and in dark mode; the chips are readable and use the brand colors
- [x] Changing an item with `curl` updates the page within the 3-second poll, without a reload
- [x] A claim put through `start_claim` and two `fail_claim` calls shows Needs a handler in the queue and on its page, and the filter finds it
- [x] A claim page with `read` steps shows the "What the agent read" panel
- [x] The queue page and the claim page have no horizontal scroll at 1280 and 390 pixels wide, and no console errors
- [x] Committed, with the pre-commit hook passing

## Phase 6: End-to-end tests, a live run and the documents

Proves the whole thing without a model, runs it once with the real one, and brings the documents up to date.

- **Playwright** (`e2e/`), standing in for the agent through the API as the pilot's tests do: a run with a to-do list that fills in and gets ticked off while the browser watches; a trial run capped at 2, where a third `take_claim` is refused and the others stay waiting; a claim that fails twice and shows Needs a handler; a claim with `read` steps showing the panel; the instructions page showing both texts. The pilot's tests keep passing.
- **Live run**, after you say it is fine to spend the tokens: delete `backend/undercover.db`, `npm run dev`, then start a run capped at 5 from the dashboard (or `uv run -m agent.main queue --limit 5`) on the default model.
- **Documents**: `docs/SPEC.md` (the claims manual is no longer "Not for now"; the queue run, the to-do list, the Needs a handler status and the retry rules are described), `docs/TECH_STACK.md` (the model, the two agents, the middleware), `docs/STATUS.md` (what is built, how to run a trial, the live run's results and what went wrong), and the `README.md` section on running it.

Success criteria:

- [x] `npm run e2e` passes, still on its own ports and database, and does not change `backend/undercover.db`
- [x] The e2e test for the cap fails if I temporarily remove the cap check from `take_claim` (checked once, then restored; not committed)
- [x] **Live**: after a reseed, a run capped at 5 on `deepseek/deepseek-v4.1-flash` works 5 claims on its own; 20 claims are still waiting; the run ends with a summary
- [x] **Live**: in the browser I see the to-do list fill in and get ticked off, and each of the 5 claims shows its steps and "What the agent read"; I report what the agent read on a few claims and whether it looked in the manual
- [x] **Live**: no claim is left in progress, no claim has two decisions or two payments, and any payout over $1,000 is held for sign-off (checked through the API)
- [x] I report the live run's time (cost is not measured: the pilot has no token or cost record), any failures and retries that happened, and what was wrong with its decisions that I can see without `data/evals/`. Accuracy against the handlers is not measured here
- [x] `docs/SPEC.md`, `docs/TECH_STACK.md` and `docs/STATUS.md` describe the product as it now is, and every box in this file is ticked
- [x] `npm run check` passes, including ruff, pyright, pytest at 80% or better, Prettier, ESLint, tsc, vitest at 80% or better and Playwright, and I report the output
- [x] `git status` shows no stray files (no database, no `test-results`)
- [x] Committed, with the pre-commit hook passing. Nothing is pushed

## Not in this build

Scoring against `data/evals/`, tools that calculate payouts, a place to read the queue agent's own steps, running claims in parallel, sign-in, real payments, messages to customers, and a way to edit the instructions from the dashboard. Each is either in the spec's "Not for now" or belongs to a later brief.

## Risks

- **A small model and a long run.** DeepSeek V4.1 Flash is cheap and fast but may skip `write_todos`, ignore `check_queue` or work claims out of the cap. The rules that matter (cap, retry, missed claims, payment) are in code, so the worst case is a messy to-do list, not a wrong payment. The call limits and the five-claim live run keep the cost small.
- **Whether the model looks things up.** The claim agent may read the wording and miss the manual, which is how the manual's rules (third claim, wild animals, meals without receipts) get skipped. The `read` steps make that visible in the live run. If it happens I will say so and propose a change to the instructions, not hide it.
- **Reasoning effort through OpenRouter.** I have not checked that `deepseek/deepseek-v4.1-flash` takes `reasoning_effort="low"` as the pilot's model did. The live run will show it; if the provider rejects it I will stop and ask.
- **The `after_model` hook.** I read the signature but have not used it with `create_agent`. If it cannot send the agent back to work, the fallback is a loop in `queue_run` that runs the agent again with the missed claims named, with the same limit of three. The criteria are written so both pass.
- **The status count in the e2e tests.** The queue page gains a fifth status, so the pilot's tests that count buttons may need updating. The tests would be changed to match the new status, not weakened.
- **Pre-commit time.** The hook runs every Python and TypeScript check on each commit; phases that touch both take a minute or two.
