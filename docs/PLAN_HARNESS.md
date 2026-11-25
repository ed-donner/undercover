# Plan: the agent's harness

This plan builds `docs/HARNESS.md` on the pilot as it stands (`docs/STATUS.md`). The UnderCover Agent stops being fed one claim at a time by our code and starts organizing its own work: one run works the queue, plans it as a to-do list the team can watch, hands each claim to a fresh subagent, looks up the sections of the claims manual and the wording it needs, and recovers from failures without leaving a claim stuck.

## The approach

### Two agents, one harness

- **The queue agent** (the orchestrator) is a `create_agent` with four tools: `list_waiting_claims`, `write_todos`, `work_claim` and `finish_run`. It never reads a claim itself. It plans, delegates, tracks and summarizes.
- **The claim agent** (the subagent) is a new `create_agent` for every call to `work_claim`, with a fresh thread and only the claim tools. Its context starts clean, so the cost of a step does not grow as the run goes on. `work_claim` is plain Python: it starts the claim, streams the claim agent, posts each step to that claim, checks the outcome and returns one line, such as `CLM-1001: approve, $420.00, paid` or `CLM-1004: failed (the model provider timed out), back in the queue`.
- **No new framework.** Both are LangChain's `create_agent`, which is already our stack. `deepagents` is installed for the labs, but the brief asks us to build these pieces into our own agent, so we don't use it.

### What lives in code and what lives in the prompt

The rules that must always hold go in code, where a model cannot talk its way around them. The judgment goes in the instructions.

| Concern | Where it lives |
|---|---|
| One decision per claim, payment once, sign-off over $1,000 | Backend, as in the pilot |
| A failed claim goes back to waiting; a second failure leaves it for a handler | Backend (`release_claim` counts attempts) |
| The cap on a run | `work_claim` refuses a new claim once the run has worked its cap |
| The check for missed claims | `finish_run` refuses while a waiting claim in scope is still unworked within the cap |
| Nothing left in progress if the run itself crashes | The runner releases any claim the run left in progress, then marks the run failed |
| Order of claims, the to-do list, the summary | The queue agent, from its instructions |
| How to decide a claim and which sections to read | The claim agent, from its instructions |

### Middleware

From LangChain's built-in middleware, on both agents:

- `ModelRetryMiddleware` retries timeouts and errors from the model provider with backoff (2 retries).
- `ToolRetryMiddleware` retries a tool call that fails to reach the backend (a connection error, not a refusal: refusals still come back to the model as text, as in the pilot).
- `ModelCallLimitMiddleware` on the claim agent caps a claim at 25 model calls, so a model stuck in a loop ends the claim instead of the run. A claim that hits it ends without a decision and goes back in the queue.

We write our own `write_todos` tool rather than using `TodoListMiddleware`: its items have three states (`pending`, `in_progress`, `completed`) and live in the agent's memory, while the brief needs a fourth state, "left for a handler", and a list the dashboard can read. Ours stores the list in the backend.

### Runs and the to-do list

A new `runs` table holds each run: its scope (the queue with a cap, or one named claim), its status (`running`, `finished`, `failed`), the to-do list as JSON, the summary and the times. One run at a time: starting a second while one is running returns 409. Each to-do item is `{claim_id, content, status}` with status `todo`, `in_progress`, `done` or `handler`. The queue page shows the latest run.

Starting a run:

- From the dashboard: Run the queue on the queue page, with the cap (default 5), calls `start_run`.
- From the dashboard: Run agent on a waiting claim calls `run_agent` as before, which now starts a run scoped to that one claim.
- From the command line: `uv run -m agent --cap 5` or `uv run -m agent CLM-1001`. Both create the run through the API, so they show on the dashboard the same way.

### A failed claim

`release_claim` adds the problem as a step and counts the attempt. After the first failure the claim goes back to `waiting`; after the second it goes to a new state, `needs_handler`, shown as "Left for a handler" in Raspberry. The queue agent sees the outcome in `work_claim`'s one-line reply, and its instructions tell it to retry a claim that went back to the queue once, later in the run, and to mark a claim left for a handler as such on the list. A retried claim does not count again against the cap. `start_claim` no longer deletes earlier steps: it adds an "Attempt 2" marker, so every step of every attempt stays on the claim.

A claim is never decided or paid twice: the backend already refuses a second decision or payment, and only a claim that failed before it was decided goes back to waiting.

### Looking things up

The manual (`data/claims_manual.md`) is seeded alongside the wording. Two new read operations split both documents on their `## ` headings:

- `list_sections(document)`: the numbered titles, a table of contents (`policy-wording` or `claims-manual`)
- `read_section(document, number)`: one section's text

The claim agent gets these in place of `get_policy_wording`, so it reads the contents and then only the sections it needs. The runner posts each `read_section` as a step of a new kind, `read` ("Claims manual, 9. Repeat claims"), and the claim page lists them under What the agent read. The dashboard still reads the whole wording through `get_policy_wording` to show the decision's section.

### Instructions

`backend/instructions.md` becomes two files, `backend/instructions/queue.md` and `backend/instructions/claim.md`, and `get_instructions` returns both. The Instructions page shows both, read only. The claim instructions are rewritten from the wording and the manual (never from `data/evals/`): the order of work from manual section 4, when to read which section (a third claim in 12 months, wild animals, meals without receipts, documents that disagree with the story, the required documents table), and the payout steps. They point to the sections rather than copying them, so the agent looks them up.

### The model

`deepseek/deepseek-v4.1-flash` with low reasoning effort becomes the default for both agents. `MODEL_NAME` still overrides it. Calls get a 60 second timeout, so a hung call becomes an error that the retry middleware handles.

### Claim states

| State | API value | Color | How a claim gets there |
|---|---|---|---|
| Waiting | `waiting` | Cerulean | Seeded; or its first attempt failed |
| In progress | `in_progress` | Marigold | `work_claim` called `start_claim` |
| Waiting for sign-off | `awaiting_signoff` | Coral | Approved with a payout over $1,000 |
| Decided | `decided` | Sea Green | Declined, referred, approved up to $1,000, or signed off |
| Left for a handler | `needs_handler` | Raspberry | Its second attempt failed |

A handler can see why a claim was left for them on its page, from its steps. Working such a claim by hand in the dashboard is not in the brief, so it is not built.

### New and changed API operations

| Method and path | `operation_id` | Used by |
|---|---|---|
| `POST /api/runs` `{cap}` | `start_run` | dashboard |
| `GET /api/runs/latest` | `get_latest_run` | dashboard, command line |
| `GET /api/runs/{run_id}` | `get_run` | runner, command line (added in the build: the runner reads its own run's scope and cap) |
| `POST /api/runs/{run_id}/todos` `{todos}` | `write_todos` | queue agent |
| `POST /api/runs/{run_id}/finish` `{summary}` | `finish_run` | queue agent, runner |
| `POST /api/runs/{run_id}/fail` `{problem}` | `fail_run` | runner |
| `GET /api/documents/{document}/sections` | `list_sections` | claim agent |
| `GET /api/documents/{document}/sections/{number}` | `read_section` | claim agent |
| `POST /api/claims/{claim_id}/run` | `run_agent` | dashboard (now starts a one-claim run) |
| `POST /api/claims/{claim_id}/release` | `release_claim` | runner (now counts attempts) |
| `GET /api/instructions` | `get_instructions` | both agents, dashboard (now both sets) |

Every operation keeps an `operation_id`, a one-line docstring and no optional inputs. A queue run's scope is every waiting claim; a one-claim run's scope is that claim.

### How the tests drive both agents with one stub

`work_claim` runs the claim agent inside the queue agent's tool call, so the calls happen in a fixed order. One scripted stub model serves both: the queue agent's replies, then the claim agent's replies for the first claim, then the queue agent again. This lets a single test script a whole run, including a claim agent that raises an error partway, without calling a model.

### Out of scope

Everything the brief doesn't ask for: scoring the agent against `data/evals/`, sign-in, real payments, messages to customers, running claims in parallel, and handling a claim left for a handler in the dashboard. Nothing here opens `data/evals/`.

## Phase 1: the backend for runs, retries and lookups

Add the `runs` table, the attempts column on claims, the `needs_handler` state and the `read` step kind. Seed the manual. Build the run operations, the section lookups and the new release rule. Split the instructions into `queue.md` and `claim.md` (first drafts here; Phase 2 writes the claim instructions in full).

- [x] `npm run seed` stores the claims manual; a test still checks that nothing under `data/evals/` is read
- [x] `list_sections("claims-manual")` returns the 14 numbered titles and `list_sections("policy-wording")` the 12; an unknown document returns 404
- [x] `read_section("claims-manual", "9")` returns "9. Repeat claims" and its text only; an unknown number returns 404
- [x] `start_run` with a cap creates a `running` run with an empty to-do list; a second `start_run` while one is running returns 409; a cap below 1 returns 422
- [x] `write_todos` stores the list and `get_latest_run` returns it; an unknown status in an item returns 422; writing to a finished run returns 409
- [x] `finish_run` stores the summary and the time; `fail_run` marks the run failed with the problem
- [x] `release_claim` on a first failure puts the claim back to `waiting` with the problem as a step; on a second it moves it to `needs_handler`
- [x] `start_claim` keeps earlier steps and adds an "Attempt 2" marker on a retry
- [x] `record_step` accepts the `read` kind
- [x] `get_instructions` returns `{queue, claim}`
- [x] The OpenAPI test still passes: every route has an `operation_id`, a docstring and no optional input
- [x] `npm run check:python` passes with coverage of at least 80%

## Phase 2: the claim agent

Refactor `agent/main.py` into `agent/claim.py` (the claim agent and `work_claim`) and shared helpers. The claim agent's tools: `get_claim`, `get_policy`, `get_claim_history`, `list_sections`, `read_section`, `record_decision` and `pay_claim`. Add the three middlewares, the new default model and the timeout. `work_claim(run, claim_id)` starts the claim, streams the agent with a fresh thread, posts steps (including `read` steps), and on an exception or a run with no decision calls `release_claim`. It never raises; it returns one line. Write `claim.md` in full from the wording and the manual.

- [x] A stub run on CLM-1001 reads the claim, policy and history, lists the wording's sections, reads two sections, decides and pays; it returns `CLM-1001: approve, $420.00, paid` and the steps include two `read` steps naming the sections
- [x] A stub model that raises partway: the claim is back to `waiting` with an error step, and `work_claim` returns a line saying so without raising
- [x] The same claim failing again moves to `needs_handler` and the line says it is left for a handler
- [x] A stub that ends without recording a decision: the claim goes back to `waiting`
- [x] A stub that hits the model call limit: the claim goes back to `waiting`
- [x] A transient model error (a stub that fails once then succeeds) is retried by the middleware and the claim is decided
- [x] A stub that approves over $1,000 and tries to pay leaves the claim `awaiting_signoff` and unpaid, as in the pilot
- [x] The claim agent's tools are exactly the seven above; none reads a file
- [x] The system prompt is `claim.md` as served by the backend (a test changes the served text and sees it)
- [x] `deepseek/deepseek-v4.1-flash` with low reasoning effort is the default; `MODEL_NAME` overrides it
- [x] `claim.md` covers the order of work, when to read which section of the manual, and the payout steps, and draws on nothing in `data/evals/`
- [x] `npm run check:python` passes

## Phase 3: the queue agent

Build `agent/queue.py`: the queue agent with `list_waiting_claims` (the waiting claims in the run's scope, with id, type, summary, amount and attempts), `write_todos`, `work_claim` and `finish_run`, with `queue.md` as its prompt. `run_queue(run_id, llm)` streams it; if it raises, the runner releases any claim the run left in progress and calls `fail_run`. If it stops without calling `finish_run`, the runner finishes the run with a note saying so. Wire `start_run` and `run_agent` to start it in the background, and the command line to `uv run -m agent --cap 5` and `uv run -m agent CLM-1001`.

- [x] A stub run capped at 2 on a fresh queue: the agent writes a to-do list of 2 claims, works both, ticks them off and finishes with a summary; 2 claims are decided and the other 23 stay `waiting`
- [x] The cap holds even if the agent tries a third claim: `work_claim` refuses it and the claim stays `waiting`
- [x] A failed claim does not stop the run: with the first claim's agent raising, the second claim is still decided and the run finishes
- [x] A failed claim is retried: the to-do item goes back to `todo`, the claim is worked again later in the run and decided, and it counts once against the cap
- [x] A claim that fails twice is left for a handler: it is `needs_handler` and its to-do item is `handler`
- [x] The check for missed claims: a stub that calls `finish_run` with a claim in scope unworked is refused with the claim's id, then works it and finishes
- [x] A queue agent that raises: no claim is left `in_progress` and the run is `failed`
- [x] `run_agent` on CLM-1001 starts a run scoped to that claim alone; `list_waiting_claims` returns only that claim
- [x] `start_run` and `run_agent` start the run in the background (stubbed in tests) and refuse with 409 while a run is running
- [x] `npm run check:python` passes

## Phase 4: the dashboard

On the queue page, above the queue: a Current run panel with its status, cap and times, the to-do list with a chip for each item's state, and the summary when it finishes; and Run the queue with a number field for the cap (default 5). The queue polls the run with the queue. The claim page gets What the agent read (the `read` steps), shows `read` steps in the step list and shows the attempt markers. Add the "Left for a handler" chip and count. The Instructions page shows both sets of instructions, each under its own heading.

- [x] Vitest: the run panel shows each to-do state, the summary, an empty state before any run, and the refusal when a run is already going
- [x] Vitest: Run the queue sends the cap; the claim page lists the sections read; the new chip and count; both sets of instructions
- [x] Checked in the browser with the Playwright MCP server in light and dark mode, with a run played through the API: the list fills in and ticks off, the chips are readable, the brand holds
- [x] `npm run check:ts` passes with coverage of at least 80%

## Phase 5: end-to-end tests, docs and the live trial

Add e2e tests that play both agents through the API, as the pilot's do. Update `docs/SPEC.md` (the manual is now in, no longer "Not for now"; a run works the queue; a claim can be left for a handler), `docs/TECH_STACK.md` (the default model, the harness) and `docs/STATUS.md`. Then reseed and run the real model on a run capped at five claims, watching it in the browser.

- [x] e2e: a run started from the queue page shows its to-do list as items are written and ticked off through the API, then the summary
- [x] e2e: a claim released twice through the API shows as left for a handler on the queue and its page shows both attempts' problems
- [x] e2e: a claim's page lists the sections the agent read
- [x] e2e: the Instructions page shows both sets of instructions
- [x] The pilot's e2e tests still pass
- [x] `docs/SPEC.md`, `docs/TECH_STACK.md` and `docs/STATUS.md` describe the product as it now is
- [x] Live trial: `npm run seed`, then Run the queue with a cap of 5 on the default model. Checked with the Playwright MCP server: the to-do list fills in and is ticked off, each of the five claims shows its steps and the sections read, the run ends with a summary, and the other 20 claims stay `waiting`
- [x] `npm run check` passes in full
