# Plan: getting ready for harder claims (the harness)

Brief: `docs/HARNESS.md`. Written under `docs/PROCESS.md`: phases with checkbox success criteria, tests with each change, tests never call a model, tick off here, commit per phase, no `--no-verify`.

## Starting point and assumptions

- `docs/STATUS.md` and the code say the repo is still the hello-world skeleton: `backend/main.py` has only `GET /api/health`, `agent/main.py` has one health tool, the dashboard shows one line. `docs/PLAN.md` (the pilot's plan) does not exist. The brief assumes a built pilot (queue, claim pages, steps, instructions page, a per-claim agent, status flow). Assumption: this plan first builds the smallest pilot base the harness needs (Phase 1), in the SPEC's terms, then the harness. If the pilot is meant to arrive from somewhere else, drop Phase 1 and adapt names.
- No new framework or dependency. The agent stays LangChain `create_agent` on OpenRouter. The to-do list, the subagent and the recovery are our own small tools around it. (`deepagents` is in `pyproject.toml` but is not used.) The dashboard uses hash routing, no router package.
- The agent reaches claims, manual, instructions, to-do list and steps only through the backend API. API operations have an `operation_id`, a one-line docstring and no optional inputs.
- Claim statuses: `waiting`, `in_progress`, `awaiting_signoff`, `decided`, plus a new `left_for_handler` (failed twice). To-do item states: `todo`, `in_progress`, `done`, `left_for_handler`.
- A cap counts distinct claims. A retry of the same claim does not use up the cap. A run on one named claim is a cap of 1 on that claim.
- A claim gets 2 attempts. Failure of attempt 1 requeues it (`waiting`); failure of attempt 2 sets `left_for_handler`. A claim that was already decided is never requeued.
- Instructions are written only from `data/policy_wording.md` and `data/claims_manual.md`. `data/evals/` is not opened at any point.
- Sections: wording and manual are split on `## ` headings (wording 1-12, manual 1-14).
- Open questions: see the end.

## Design in brief

- Backend (SQLite, file from `UNDERCOVER_DB`, default `undercover.db`, git-ignored). Tables: `claims` (with `status`, `attempts`), `decisions` (one row per claim, unique), `payments` (one row per claim, unique), `steps` (per claim: tool, summary, time), `reads` (per claim: document, section), `runs` (id, cap, status, summary), `todos` (per run: text, state, claim id). Seeded from `data/*.json` except `data/evals/`.
- Double decide or double pay is blocked in the backend (unique constraint, HTTP 409), so it holds even if the model or a retry tries it. Payment over `company.json` limit ($1,000) is blocked until sign-off.
- Orchestrator agent (queue runner) tools: `list_waiting_claims`, `write_todos` (replaces the run's list), `work_claim(claim_id)`, `check_missed`. `work_claim` starts a fresh `create_agent` subagent with only the claim tools and a clean message list, runs it, and returns one line. It is the single place where exceptions are caught: it records the failure, requeues or leaves the claim for the handler, and returns `FAILED: <what went wrong>` so the run continues. The cap and the attempt limit are enforced in code in `work_claim`, not only in the prompt.
- Claim subagent tools: `get_claim`, `get_policy`, `get_customer_history`, `list_sections`, `search_manual`, `read_section`, `decide` (decision, payout, section, reason), `pay`. Every tool call is recorded as a step on the claim by one wrapper (`wrap_tool_call` middleware). `read_section` also stores a `reads` row.
- Run ends with a short summary stored on the run. After the agent says it is finished, code calls the same missed-claims check and, if a waiting claim within the cap was missed, sends the agent one reminder (at most twice) before closing the run.
- Run start and end sweep: any `in_progress` claim whose run is gone or ended is requeued (or left for a handler when attempts are used up), so nothing stays stuck even if the process dies.

## Phase 1: pilot base the harness stands on

Files: `backend/main.py` (split into `backend/db.py`, `backend/seed.py`, `backend/routes.py` only if `main.py` gets long), `data/` read only, `.gitignore`, `package.json` (`seed` script), `backend/tests/test_claims.py`.

- [x] SQLite schema and `uv run -m backend.seed` (also `npm run seed`) load the 25 claims, policies, customers, plans and company settings; reseeding resets everything (claims `waiting`, no steps, decisions, payments, runs, to-dos). `data/evals/` is never read.
- [x] API: `list_claims`, `get_claim`, `get_policy`, `get_customer_history`, `record_step`, `decide_claim`, `pay_claim`, `sign_off_claim`, `get_instructions` (replaced in Phase 6, for now a placeholder text). One-line docstrings, `operation_id`s, no optional inputs.
- [x] `decide_claim` returns 409 if the claim is already decided. `pay_claim` takes the amount, returns 409 if already paid or if the payout is over $1,000 and not signed off; sign-off moves the claim `awaiting_signoff` to `decided`.
- Tests added (`backend/tests/`): seed count and reseed reset; decide twice gives 409; pay twice gives 409; $1,000 pays, $1,001 blocked until sign-off; no `evals` path in the seed code (grep test).
- Verify: `uv run pytest -q backend`; `uv run -m backend.seed` prints 25 claims; `GET /api/claims` returns 25 `waiting`.

## Phase 2: manual and wording lookup (item 4)

Files: `backend/docs_lookup.py`, `backend/main.py`, `backend/tests/test_lookup.py`.

- [x] Split `data/claims_manual.md` and `data/policy_wording.md` into numbered sections by `## ` headings at start-up.
- [x] API: `list_sections(document)` (number and title only), `search_sections(document, query)` (matching section numbers, titles and a one-line snippet, no full text), `read_section(claim_id, document, number)` (full section text; stores a `reads` row on the claim and a step).
- [x] `get_claim` returns the claim's `reads` so the dashboard can show them.
- Tests: list returns 14 manual and 12 wording sections; search for "wild animal" finds manual section 7; `read_section` returns only that section (not the whole document) and a repeated read stores one row; unknown section gives 404.
- Verify: `uv run pytest -q backend`; `curl` the three operations and see small payloads.

## Phase 3: runs, to-do list and recovery state in the backend (items 2, 5)

Files: `backend/main.py`, `backend/runs.py`, `backend/tests/test_runs.py`.

- [x] API: `start_run(cap)` (cap 0 not allowed; a named claim run is `cap=1` with that claim), `get_current_run` (run, summary, to-do list), `write_todos(run_id, items)` (replaces the list; each item has text, state, optional claim id), `finish_run(run_id, summary)`.
- [x] API: `start_claim(run_id, claim_id)` sets `in_progress`, attempts + 1, refuses a claim that is not `waiting` or is over the cap. `fail_claim(claim_id, reason)`: attempts below 2 gives `waiting`, otherwise `left_for_handler`, and sets the matching to-do item; a decided claim is left alone. `sweep_stuck()` requeues stuck `in_progress` claims by the same rule; called by `start_run` and `finish_run`.
- [x] `list_waiting_claims(run_id)` returns waiting claims within the run's cap (includes requeued ones) and `check_missed(run_id)` returns the waiting claims within the cap that the run has not worked.
- Tests: to-do list is stored and returned with its states; cap blocks the (cap+1)th distinct claim; requeue after one failure and `left_for_handler` after two; decided claim not requeued; sweep fixes a stuck claim; missed-claims returns the unworked waiting ones.
- Verify: `uv run pytest -q backend`.

## Phase 4: model default and agent plumbing (item 6)

Files: `agent/main.py` (split: `agent/model.py`, `agent/tools.py`, `agent/steps.py` only as needed), `agent/tests/test_agent.py`.

- [x] `DEFAULT_MODEL = "deepseek/deepseek-v4.1-flash"`, low reasoning effort by default; `MODEL_NAME` overrides (as today, no reasoning effort then). Add a client timeout and `max_retries` for provider errors and timeouts.
- [x] Remove the health-only tool and prompt; keep the backend client helper.
- [x] Step recorder: one `wrap_tool_call` middleware that posts every claim tool call (tool, short args, short result, or the error) to `record_step`.
- Tests: default model name and effort, `MODEL_NAME` override (replace the existing `openai/gpt-6-luna` test); the middleware records a step for a stub tool call and records an error step when the tool raises.
- Verify: `uv run pytest -q agent`.

## Phase 5: claim subagent and queue runner (items 1, 3, 5)

Files: `agent/claim_agent.py`, `agent/runner.py`, `agent/cli.py`, `package.json` (`run` script), `agent/tests/test_runner.py`.

- [x] `work_claim(claim_id)` tool: `start_claim`, build a fresh claim subagent (tools above, clean messages, thread id per attempt), invoke, return one line (`CLM-1004: approved $215` or `CLM-1004: declined`, `referred`, or `FAILED: <reason>`). On any exception it calls `fail_claim` and returns the failed line. Return value never contains the subagent's message history.
- [x] Queue runner agent with `list_waiting_claims`, `write_todos`, `work_claim`, `check_missed`; chooses the order; ends with a short summary stored via `finish_run`.
- [x] `run(limit=None, claim_id=None, llm=None)`: starts the run, invokes the runner, applies the missed-claims backstop (up to two reminders), finishes the run, sweeps. If the runner itself errors (provider error), the run is sweep-cleaned and finished as failed, never leaving a claim `in_progress`.
- [x] CLI: `uv run -m agent.cli --limit N` and `--claim CLM-1001`; `npm run run -- --limit 5`. The old `run(claim_id, thread_id)` entry becomes `run(claim_id=...)`.
- Tests (stub model, in-process backend via `TestClient`, no network): runner writes a to-do list and it is readable via `get_current_run`; cap of 2 on 4 waiting claims works exactly 2 and leaves 2 `waiting`; a claim whose stub raises a provider error does not stop the run and the next claim is worked; that claim is `waiting` and gets retried and decided; a claim failing twice is `left_for_handler`, the run still completes; no claim decided or paid twice when the stub tries; missed-claims backstop triggers a reminder when the stub finishes early, and the missed claim is then worked; subagent history is not carried into the runner; `claim_id` run works one claim.
- Verify: `uv run pytest -q agent`; coverage stays at or above 80%.

## Phase 6: instructions (item 7)

Files: `backend/instructions/queue_runner.md`, `backend/instructions/claim.md`, `backend/main.py` (`get_instructions` returns both), `agent/` (loads them via the API), tests.

- [x] Write queue-runner instructions: work the waiting claims within the cap, choose the order, write and update the to-do list, give each claim to `work_claim` one at a time, read the one-line results, never decide a claim itself, run the missed-claims check before finishing, finish with a short summary for handlers (decided, awaiting sign-off, left for a handler, still waiting).
- [x] Write claim instructions from the manual section 4 order and the wording: look up only the sections needed (list, search, then read), the 90-day rule, documents (manual 5), payout order (wording 10, manual 6), the interpretation notes, referral rules (manual 8, 9), $1,000 sign-off (manual 3), customer data (manual 11), and to decide with a reason and the section relied on. No text copied from or informed by `data/evals/`.
- Tests: `get_instructions` returns both texts; both mention the cap check / sections lookup and sign-off; a test that the instruction files exist and do not mention the evals folder.
- Verify: `uv run pytest -q`; read both files against the manual once.

## Phase 7: dashboard (items 2, 3, 4, 7)

Files: `dashboard/src/App.tsx` (split into `QueuePage.tsx`, `ClaimPage.tsx`, `InstructionsPage.tsx`, `api.ts`), `dashboard/src/*.test.tsx`, `e2e/queue.spec.ts`, `playwright.config.ts` (test backend with its own seeded DB, no model).

- [ ] Hash routes: `#/` queue, `#/claims/CLM-1001`, `#/instructions`, styled per `docs/BRAND.md`.
- [ ] Queue page: all claims with status (waiting, in progress, awaiting sign-off, decided, left for handler); the current run's summary and to-do list with the four states, refreshed by polling every 2 seconds while a run is active.
- [ ] Claim page: decision, payout, reason, section relied on, attempts, every step in order, and "Read" list showing document and section numbers and titles.
- [ ] Instructions page: queue-runner and per-claim instructions, read only.
- Tests (vitest, mocked fetch, strict TS, no `any`): queue renders statuses and a to-do list with each state and updates on the next poll; claim page shows steps and sections read; instructions page shows both. Playwright: seed, call backend operations directly to write a to-do list and a step and a read, then check the pages (no model).
- Verify: `npm run check:ts`; `npm run e2e`; look at each page in the browser with the Playwright MCP server.

## Phase 8: documents

Files: `docs/SPEC.md`, `docs/TECH_STACK.md`, `docs/STATUS.md`.

- [ ] SPEC: remove the manual from "Not for now"; decisions follow the wording and the manual; add the run with a cap, the to-do list, subagent per claim, sections read shown on the claim, recovery rules, the new statuses, the instructions page; keep the $1,000 rule and the evals rule.
- [ ] TECH_STACK: default model `deepseek/deepseek-v4.1-flash` with low reasoning effort, `MODEL_NAME` override; the orchestrator plus subagent; SQLite tables; no new framework.
- [ ] STATUS: what is built, how to seed (`npm run seed`), run (`npm run run -- --limit 5`), and check.
- Verify: read the three against the code; commands in STATUS run.

## Phase 9: full check and live 5-claim trial

- [ ] `npm run check` is green (ruff, pyright, pytest with 80% coverage, ESLint, Prettier, tsc, vitest, Playwright), with no thresholds lowered or rules disabled.
- [ ] Stub tests exist for each new behavior: to-do list stored and shown (Phases 3, 5, 7), run cap, failed claim does not stop the run, requeue and retry, left for a handler after two failures, missed-claims check.
- [ ] Reseed first: `npm run seed`, then check 25 claims `waiting`. Needs `OPENROUTER_API_KEY` in `.env`; the real model is used only here and only with `--limit 5`.
- [ ] `npm run run -- --limit 5` (default model, no `MODEL_NAME`): exactly 5 claims worked on their own, 20 still `waiting`, no claim `in_progress`, none decided or paid twice, payouts over $1,000 not paid without sign-off.
- [ ] Browser check while it runs and after: the queue page shows the to-do list filling and being ticked off; each worked claim page shows its steps and the sections read; the 20 other claims show waiting; the instructions page shows both texts.
- [ ] If a failure shows up, fix it and, for a new live run, reseed and cap at 5 again.
- [ ] Tick all boxes in this file, update `docs/STATUS.md`, commit (hook passes).

## Open questions

1. The pilot is not in the repo (no `docs/PLAN.md`, skeleton only). Is building its base inside this plan (Phase 1) what is wanted?
2. Is `left_for_handler` a new claim status, or should it map to an existing one? Assumed new.
3. Should a retry happen in the same run (assumed yes, once the claim is back in the queue) or on the next run?
4. `data/policy_wording_short.md` exists; the plan uses the full wording split into sections.
