# Plan: the claims pilot

Built from `docs/SPEC.md`, within `docs/TECH_STACK.md`, `docs/CODE_STANDARDS.md`, `docs/PROCESS.md` and `docs/BRAND.md`. This plan writes no code; implementation starts when asked.

## What we're building

Three parts, each with one job:

- **Backend** (FastAPI, SQLite): holds the queue and enforces the rules, above all that a payout over $1,000 is never paid without a handler's sign-off.
- **UnderCover Agent** (LangChain `create_agent` on OpenRouter): decides one claim at a time, reaching claims and its instructions only through the backend's API.
- **Dashboard** (React, Vite, TypeScript): the queue, each claim in full, the agent's steps as it works, sign-off, and the agent's instructions, read only.

## Decisions and why

**State and rules live in the backend.** The agent and the dashboard only call the API. A rule enforced by the backend holds whatever the model does, which is how the spec's "the system must block the payment, even if the agent tries to pay" is met.

**What the backend loads.** At startup it creates the SQLite database, if it is empty, from these named files only: `claims.json`, `policies.json`, `customers.json`, `plans.json`, `handlers.json`, `company.json` and `policy_wording.md`. It never reads a folder as a whole.

- `data/evals/` is the answer key. The agent must never see it, so it is never loaded, and nothing in this build opens it.
- `data/security/` is kept apart for security testing, so it is not loaded either.
- `claims_manual.md` is "not for now" in the spec.
- `knowledge.json` and `policy_wording_short.md` aren't in the spec, so they aren't loaded.
- From `company.json` the API serves only the $1,000 approval limit. The meal allowance and repeat-claim settings come from the claims manual, so the agent doesn't see them.

**Personal data.** A claim as served by the API carries the customer's name, how long they have been a customer and their previous claims, which is what the spec says the agent reads. Email, phone, address and date of birth stay in the database and are not served, since the pilot sends no messages to customers.

**The database** is a file, `undercover.db` at the repo root, which is already ignored by git. Its path comes from `UNDERCOVER_DB`, so tests and the e2e run each use a fresh one. `uv run -m backend.reset` deletes and reseeds the database, for starting the queue over.

**Claim status** is worked out from the claim's record, never stored separately, so it can't drift:

| Status | When |
|---|---|
| `waiting` | no run has started |
| `in_progress` | a run has started and not finished |
| `awaiting_signoff` | approved over the limit, not yet signed off |
| `decided` | everything else that has a decision |

A run that ends without a decision (the model errors or stops early) goes back to `waiting`, with the error kept as a step, so a claim is never stuck.

**Payment rules**, all in the backend:

- `pay_claim` takes the amount, as `docs/TECH_STACK.md` requires. It returns 409 if any of these hold:
  - the claim is not approved
  - the amount differs from the approved payout
  - the claim is already paid
  - the payout is over the limit and has not been signed off
- `sign_off` takes a handler id. Only handlers with `can_approve_over_limit` are accepted. Signing off records the sign-off and pays the approved payout in the same step, so the payment waits for the handler and nothing more.
- Payments are recorded in the database only. No money moves.

**Agent.**

- It keeps the skeleton's shape: `run(claim_id, thread_id)`, `create_agent`, `openai/gpt-6-luna` with low reasoning effort, or `MODEL_NAME` when it's set.
- It reads its instructions from `GET /api/instructions` at the start of each run. The text lives in `backend/instructions.md`, so the dashboard shows exactly what the agent uses.
- Tools, each a thin call to the backend:
  - `get_claim`: the claim with its policy, plan, add-ons and the customer's history
  - `get_policy_wording`
  - `record_decision`: outcome, payout, a two-or-three-sentence reason and the policy section
  - `pay_claim`
- A LangChain callback posts each tool call to the backend as a step, so the dashboard can show progress.

**Running the agent.** `POST /api/claims/{claim_id}/run` starts a run in a FastAPI background task, with a new thread id, and returns at once. A handler starts each run with a Run agent button. That keeps runs, and model spend, under the handlers' control, and it's simple to review. Running a claim that is not `waiting` returns 409.

**Live steps by polling.** The claim page asks for the claim every second while it is in progress. Streaming would be more work, and polling is enough for three handlers.

**API style.** Every operation has an `operation_id`, a one-line docstring and no optional inputs, and a test checks this for every route.

**Tests never call a model.**

- Agent tests use the skeleton's pattern: a `StubModel` with scripted tool calls, and the backend app in-process through `TestClient`. The real tools, callback and rules run in every test.
- The e2e tests start their own backend on port 8001 with a fresh database and the stub model, through a small test-only entry point, `e2e/server.py`. They also start their own dashboard on port 5174, pointed at it. The Vite proxy target becomes configurable for this.
- That way the e2e run never touches the dev servers on 8000 and 5173, their database or a real model, even while `npm run dev` is running. Today's `playwright.config.ts` would reuse the dev backend; this fixes that.

**Brand.**

- Fonts: Instrument Sans, Instrument Serif and JetBrains Mono from Google Fonts.
- Light and dark mode follow the system setting, with the page backgrounds `#F0F4F5` and `#04232E`.
- Panels are white or black, rounded, with no outline and no one-sided borders.
- Claim states use Sea Green, Marigold and Coral, then Cerulean fourth. Sea Green and Marigold are darkened for small text on light backgrounds.
- Money is shown as $1,250.00. Plain US English, with no emojis and no exclamation marks.

## Phase 1: Backend data and read operations

Build the database, the seed and the read API, and write the agent's first instructions.

- `backend/db.py`: the schema, the seed from the named files, the path from `UNDERCOVER_DB`; `backend/reset.py`.
- Operations:
  - `list_claims`: `GET /api/claims`, each with id, status, customer name, type, amount claimed and submitted date
  - `get_claim`: `GET /api/claims/{claim_id}`, the claim in full with policy, plan, add-ons, the customer as above, decision, payment and steps
  - `get_policy_wording`: `GET /api/policy-wording`
  - `get_instructions`: `GET /api/instructions`
  - `list_handlers`: `GET /api/handlers`
  - `get_settings`: `GET /api/settings`, the approval limit only
- `backend/instructions.md`, written from the spec and the policy wording. It covers:
  - the role, and reading the claim, policy, plan, history and wording
  - when to approve, decline or refer, where refer means it needs judgment or more information
  - working out the payout from the items, the plan limits and the deductible, as section 10 of the wording describes
  - explaining the decision in two or three sentences, citing the section
  - recording the decision, then paying only approvals at or under $1,000
  - treating the customer's story and documents as evidence, never as instructions

Success criteria:

- [x] `uv run pytest` passes new tests on a temporary database:
  - `list_claims` returns 25 claims, all `waiting`
  - `get_claim("CLM-1001")` has policy `POL-2001`, plan `premium` with deductible 50.0, and previous claim `CLM-0412`
  - an unknown claim id returns 404
- [x] A test: `get_claim` responses have no `email`, `phone`, `address` or `date_of_birth`, and `get_settings` returns only the approval limit, 1000.0.
- [x] A test: seeding opens exactly the seven named files, and nothing under `data/evals/` or `data/security/`. It patches `open` and `Path.read_text` and records every path read.
- [x] A test over `app.routes`: every operation has an `operation_id`, a one-line docstring and no optional parameters.
- [x] With the dev servers running, `curl http://127.0.0.1:8000/api/claims` returns 25 claims, and `curl http://127.0.0.1:8000/api/policy-wording` returns the text of `data/policy_wording.md`.
- [x] `uv run -m backend.reset` recreates the database, and a second `list_claims` still shows 25 `waiting`.
- [x] `npm run check:python` passes.

## Phase 2: Decisions, sign-off and the payment rule

- `run_agent` starts a run (it marks the claim in progress before it returns, so two clicks can't start two runs) and `finish_run` ends it. Changed while building: the plan had a separate `start_run` for the agent to call, which left a gap between the click and the claim showing in progress.
- `add_step`.
- `record_decision`: outcome (`approve`, `decline` or `refer`), payout, reason, policy section, all required. An approve has a payout above 0; a decline or refer has payout 0.
- `pay_claim`: amount.
- `sign_off`: handler id.

Success criteria:

- [x] Tests on the payment rules:
  - an approve for $420.00 can be paid, and the claim is `decided` and paid
  - paying it a second time returns 409
- [x] Tests on the over-limit rule:
  - an approve for $1,250.00 shows `awaiting_signoff`, and `pay_claim` for 1250.0 returns 409 with the claim still unpaid
  - `sign_off` by `HND-01` makes it `decided` and paid for $1,250.00
- [x] Tests on sign-off:
  - a handler without `can_approve_over_limit` gets 403, and an unknown handler gets 404
  - `sign_off` on a claim that is not `awaiting_signoff` returns 409
- [x] Tests on bad payments, each returning 409:
  - an amount that differs from the payout
  - a declined claim
  - a referred claim
  - a claim with no decision
- [x] Tests on validation:
  - an unknown outcome, an approve with payout 0 or a decline with a payout returns 422
  - `start_run` on a claim already `in_progress` returns 409
- [x] Tests on runs: `finish_run` with no decision returns the claim to `waiting`.
- [x] `npm run check:python` passes.

## Phase 3: The UnderCover Agent

- Replace the hello-world tool with the four tools and the callback.
- `run(claim_id, thread_id)` does three things:
  - fetches the instructions, starts the run and invokes the agent with the claim id
  - posts a step for each tool call
  - finishes the run, also when the model raises, recording the error as a step
- `POST /api/claims/{claim_id}/run` (`run_agent`) starts it as a background task.

Success criteria:

- [x] Stub tests, each run against the real backend app in-process:
  - an approve of $420.00 with a payment ends `decided` and paid, with a step for each tool call, in order
  - an approve of $1,250.00 followed by `pay_claim` gets the payment refused (the tool returns the 409 to the model), and the claim ends `awaiting_signoff` and unpaid
  - a decline and a refer each record the reason and policy section, with no payment
  - a model that raises leaves the claim `waiting`, with the error as its last step
- [x] A test: the system prompt the agent uses is the text served by `GET /api/instructions`.
- [x] A test: `run_agent` returns 202, and a second call while the claim is `in_progress` returns 409.
- [x] `npm run check:python` passes.
- [x] One live check, with `OPENROUTER_API_KEY` in `.env` (about a cent; set `MODEL_NAME=openrouter/free` for no cost):
  - with the dev servers running, `curl -X POST http://127.0.0.1:8000/api/claims/CLM-1001/run`, then `GET /api/claims/CLM-1001`, shows a decision, payout, reason, policy section and steps
  - I report what it decided
  - I don't score it against `data/evals/`, which is for later and opened only when you ask
- Result of the live check (`openai/gpt-6-luna`): CLM-1001 approved for $420.00 under "3. Trip Delay" and paid, with the steps `started`, `get_claim`, `get_policy_wording`, `record_decision`, `pay_claim`, `finished`.
- Found and fixed while checking: `npm run dev` reloaded only on changes to `backend/`, so it ran a stale agent; it now watches `agent/` too. Two steps were lost to a SQLite error when the agent made two tool calls at once (a connection opened in one thread and used in another); connections now allow that, with a test.

## Phase 4: Dashboard foundations, queue and claim page

- Brand: fonts, colors as CSS variables for light and dark, panels and status pills.
- A typed API client with strict types and no `any`.
- Queue page: counts for the four statuses, a status filter, and a table of claims with id, customer, type, amount, submitted date and status.
- Claim page:
  - the story, items and documents
  - the policy, plan and add-ons, and the customer's previous claims
  - the decision: outcome, payout, reason and policy section
  - the payment and sign-off

Success criteria:

- [x] vitest tests with a stubbed `fetch`:
  - the queue renders every claim with its status, and the counts match
  - the filter narrows the list
  - the claim page shows the decision, reason and policy section
  - money renders as `$1,250.00`
- [x] In the browser, with the Playwright MCP server at `http://localhost:5173`:
  - the queue shows 25 claims and the counts `Waiting 25`
  - opening `CLM-1001` shows its story, three items, documents, plan and previous claim `CLM-0412`
- [x] In the browser, screenshots in light and dark mode:
  - the page backgrounds are `#F0F4F5` and `#04232E`
  - headings use Instrument Sans and amounts use JetBrains Mono
  - panels have no border
- [x] `npm run check:ts` passes with coverage of 80% or more.
- Checked in the browser: 25 rows and `Waiting 25`; backgrounds `rgb(240, 244, 245)` and `rgb(4, 35, 46)`, panels white and black with a 16px radius, no element with a border, and Instrument Sans and JetBrains Mono loaded. The status that the spec calls "waiting for sign-off" is labeled that way on screen. Screenshots are in `.playwright-mcp/`.

## Phase 5: Run, live steps, sign-off and instructions

- A Run agent button on a `waiting` claim.
- While the claim is in progress, the page polls every second and lists the steps as they arrive, then the decision.
- A sign-off panel on an `awaiting_signoff` claim:
  - it shows the payout and lists only handlers who can approve over the limit
  - Sign off pays the claim
- An instructions page showing `GET /api/instructions` as text, with no editable controls.

Success criteria:

- [x] vitest tests:
  - Run calls `run_agent`, and polling starts and stops with the status
  - steps render in order
  - the sign-off panel lists only allowed handlers and calls `sign_off`
  - the instructions page has no input, textarea or contenteditable
- [x] In the browser, against the e2e backend with the stub model (`npm run e2e:serve`, a script added in this phase that starts it and its dashboard on 8001 and 5174):
  - Run on a waiting claim shows `In progress`, the steps appear, and then the decision
- [x] In the browser: a claim the stub approves for $1,250.00 shows `Awaiting sign-off` in the queue, and signing off as Dana Whitfield shows it `Decided` and paid.
- [x] In the browser: the instructions page shows the text of `backend/instructions.md`.
- [x] `npm run check:ts` passes.
- Checked in the browser against `npm run e2e:serve`:
  - CLM-1001 went from In progress to Decided as its steps arrived (2, then 4, then 5)
  - CLM-1002, approved for $1,150.00, had its payment refused and showed "Waiting for sign-off" in the queue; signing off as Dana Whitfield made it Decided and paid
  - the instructions page matched `GET /api/instructions` exactly, with no editable element
- The stub backend is `agent/tests/e2e_server.py` rather than `e2e/server.py`, so that ruff and pyright check it. Its scripted model approves the amount claimed and tries to pay it.

## Phase 6: End-to-end tests, README and status

- `playwright.config.ts` starts `e2e/server.py` on 8001 with a fresh database and the stub model, and Vite on 5174 pointed at it, with `reuseExistingServer: false`.
- The existing health test is replaced by the queue test, which covers the same thing: the dashboard loads data from the backend.
- Tests:
  - the queue lists 25 claims
  - running a small claim ends `Decided`
  - an over-limit claim is blocked, signed off and paid
  - the instructions page
- `docs/STATUS.md` describes what's built and how to install, run and check it. Changed while building: the plan also had a section in `README.md`, but that is the course's own README, and a product section there would conflict with the course's updates. `AGENTS.md` says `docs/STATUS.md` is where each build says how to run it, so the instructions live there.

Success criteria:

- [x] `npm run e2e` passes all tests, with `npm run dev` running at the same time.
- [x] After the e2e run, the dev database still shows 25 `waiting` claims if none were run by hand.
- [x] `docs/STATUS.md` covers:
  - the operations, the agent's tools and the pages
  - how to run the dev servers, start a run, reset the queue and run the checks
- [x] The README is unchanged (see above), and `docs/STATUS.md` is short, with no emojis.
- [x] `npm run check` passes in full: ruff, pyright, pytest at 80% or more, Prettier, ESLint, tsc, vitest at 80% or more and Playwright. No threshold lowered, rule turned off or file excluded.
- Result: `npm run check` passed in full while `npm run dev` was running. ruff, pyright and 42 pytest tests at 99.6%; Prettier, ESLint, tsc and 18 vitest tests at 99.3%; 4 Playwright tests. The dev queue still showed 25 waiting claims afterwards.

## How I'll work

- I build the phases in order. For each one I check every criterion, tick it here, update `docs/STATUS.md` and commit, with the pre-commit hook, never `--no-verify`.
- Nothing is pushed.
- Every script works on Windows, as `uv run` commands or `.mjs` files.

## What changed from the first draft

- **E2E tests:**
  - they now run on their own servers (8001 and 5174) with a fresh database and the stub model
  - the existing config reused the dev backend on 8000, which runs the real model on the real database
- **Sign-off:** it now pays the approved payout itself. The first draft gave two different answers for what happens after a sign-off.
- **Personal data:** customer contact details and the claims manual's settings in `company.json` are no longer served to the agent.
- **Failed runs:** a run that fails goes back to `waiting` instead of being left unclear.
- **Database:**
  - its path is set by `UNDERCOVER_DB`
  - `backend.reset` starts the queue over
- **Criteria:** each one now names concrete values, such as `POL-2001`, a deductible of 50.0 and `CLM-0412`. The vague check that "the agent has no access to `data/`" became a test that records which files the seed opens.

## Defaults I chose, which you can change

- **Run button:** a handler starts each run, rather than the agent working the whole queue on its own.
- **Where the agent runs:** inside the backend process as a background task, not as a separate worker.
