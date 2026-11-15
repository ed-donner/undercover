# Plan: the harness

Source: `docs/HARNESS.md`. Standards: `docs/CODE_STANDARDS.md`. Process: `docs/PROCESS.md`.

## Starting point and one decision for review

`docs/HARNESS.md` builds on the pilot, but this repo holds only the hello-world skeleton (`docs/STATUS.md`): one health route, one health tool, one page. There is no `docs/PLAN.md` and no claims backend, so the harness has nothing to attach to.

**Approach: Phases 1 and 2 build the minimum pilot from `docs/SPEC.md`, written so the harness slots in.** The pilot's backend, queue, claim page and instructions page are needed anyway, and building them with the harness's needs in mind (steps, attempts, runs) avoids rework. The pilot's own "agent fed one claim at a time" is not built, since the harness replaces it. If you would rather check out Ed's pilot (`git checkout week1day3-end`) and plan on top of it, say so and I will rewrite Phases 1 and 2 as small additions.

## Design in brief

- **Backend (FastAPI + SQLite)** owns all state: claims, steps, runs, to-do items, attempts. Every operation has an `operation_id`, a one-line docstring and no optional inputs. The agent reaches everything through it, and the backend never reads `data/evals/`.
- **Rules live in the backend, not the prompt.** Deciding is allowed only from `in_progress`, paying only once, and paying over $1,000 only after sign-off. That is what makes "never decided or paid twice" and "blocked even if the agent tries" true whatever the model does.
- **Our own agent code, no new framework.** The queue agent is a `create_agent` with a to-do tool, a `work_claim` tool that runs a fresh `create_agent` subagent per claim (clean context, one-line result), and lookup tools. Retries and recovery are plain Python around those calls.
- **Failure handling is in code, not in the model's hands.** `work_claim` catches any failure of the subagent, calls the backend's `fail_claim`, and returns "failed" as a line. The backend counts attempts: first failure returns the claim to `waiting`, second sets `for_handler`.
- **Cap and missed-claim check are in code.** The run takes `limit`; the queue tool only offers that many claims. A final `check_queue` call in code confirms no claim within the cap is still `waiting` or `in_progress`.
- **Manual lookup.** Tools `list_sections(document)` and `read_section(document, number)` over `claims_manual.md` and `policy_wording.md`. Each read is recorded as a step so the claim page shows it.
- **Claim statuses:** waiting, in progress, waiting for sign-off, decided (SPEC), plus `for_handler` for claims the agent gave up on. SPEC is updated to say so.

## Phase 1: Backend foundation (pilot minimum)

Builds the database, seed and claim operations with the payout rules.

- Seed from `data/` (claims, policies, customers, plans, handlers, company), never `data/evals/`. `POST /api/reseed` resets the database.
- Operations: `list_claims`, `get_claim`, `get_policy`, `get_customer`, `start_claim` (waiting to in_progress), `decide_claim(claim_id, decision, payout, reason, policy_section)`, `pay_claim(claim_id, amount)`, `sign_off_claim(claim_id, handler_id)`.
- Rules: decide only from `in_progress`; over $1,000 goes to `awaiting_signoff`; pay only once and only up to the decided payout; over-limit pay blocked until sign-off.

Success criteria:
- [x] `uv run pytest backend` passes, with tests for each rule below.
- [x] After reseed, `GET /api/claims` returns 25 claims all `waiting`, and no code path in `backend/` opens `data/evals/` (`grep -r evals backend` finds nothing).
- [x] Deciding a claim twice returns 409 and leaves the first decision unchanged.
- [x] Approving $1,250.00 sets `awaiting_signoff`; `pay_claim` on it returns 409; after `sign_off_claim` the same call succeeds; a second pay returns 409.
- [x] Every operation has an `operation_id`, a one-line docstring and no optional inputs (a test walks `app.openapi()`).
- [x] `npm run check:python` is green.

## Phase 2: Backend harness operations

Adds steps, runs, to-do items, attempts, document sections and instructions.

- Steps: `add_step(claim_id, kind, text)` and steps in `get_claim`. Kinds include `read` (with document and section).
- Runs and to-do: `start_run(limit)`, `get_run`, `set_todos(run_id, items)` where each item is `{id, text, status}` with status todo, in_progress, done or for_handler; `get_current_run`.
- Recovery: `fail_claim(claim_id, error)` records a step and an attempt; attempt 1 returns the claim to `waiting`, attempt 2 sets `for_handler`. Failing a decided claim is refused.
- Queue: `list_waiting_claims(limit)` returns at most `limit` claims, counting only claims not yet worked in this run.
- Documents: `list_sections(document)`, `read_section(document, number)` for the manual and wording, split on `## N.` headings.
- Instructions: `GET /api/instructions` returns the queue and claim instructions, stored as files in `backend/instructions/`.

Success criteria:
- [x] Tests pass for: to-do list stored and returned in order and replaced on update; `limit` caps `list_waiting_claims`; first failure returns a claim to `waiting`; second failure gives `for_handler`; a decided claim cannot be failed or restarted.
- [x] `curl /api/documents/claims_manual/sections` lists 14 sections and `read_section` for section 9 returns the repeat-claims text.
- [x] `read_section` writes a `read` step visible in `get_claim`.
- [x] `npm run check:python` is green.

## Phase 3: The claim agent and its tools

Builds the subagent that works one claim, and the model change.

- `agent/tools.py`: LangChain tools wrapping the backend operations above (one tool per operation the claim agent needs).
- `agent/claim_agent.py`: `work_one_claim(claim_id, llm)` builds a fresh `create_agent` with the claim instructions fetched from the backend, runs it, and returns a one-line result (decision and payout, or what went wrong).
- Default model becomes `deepseek/deepseek-v4.1-flash` with low reasoning effort; `MODEL_NAME` still overrides. `docs/TECH_STACK.md` updated.
- Claim instructions written from `data/policy_wording.md` and `data/claims_manual.md` only: look up the sections you need, never ask for whole documents, decide, explain in two or three sentences with the policy section. Never from `data/evals/`.
- Every tool call is recorded as a step on the claim.

Success criteria:
- [x] Tests on a stub model (fake chat model emitting scripted tool calls) show: the agent reads sections, decides, and the claim ends `decided` with steps including `read`.
- [x] A test shows `model()` returns the DeepSeek default with low effort, and `MODEL_NAME=openrouter/free` overrides it.
- [x] A test shows the claim agent's prompt contains no whole document (length under a small bound) and the subagent starts with only one user message.
- [x] `grep -r evals agent` finds nothing.
- [x] `npm run check:python` is green.

## Phase 4: The queue agent

Builds the orchestrator, the to-do list, the cap, delegation and recovery.

- `agent/queue_agent.py`: `run_queue(limit, llm)` and `run_one(claim_id, llm)`. A `create_agent` with tools `list_waiting_claims`, `write_todos` (calls `set_todos`), `work_claim(claim_id)` and `finish`. The queue instructions tell it to plan the list first, choose the order, update items as it goes and end with a summary for handlers.
- `work_claim` runs the subagent in a try/except; on any exception it calls `fail_claim` and returns the failure as a line. One bad claim never raises into the run.
- Timeouts and model provider errors: retries on the model call (`max_retries` on the client) before a claim counts as failed.
- After the agent finishes, code calls `check_queue(limit)`; if any claim within the cap is still `waiting`, the agent is resumed once on those claims, then the miss is reported in the summary.
- CLI: `uv run -m agent --limit 5`, `uv run -m agent --claim CLM-1001`, and `npm run agent` scripts. Live runs reseed first.

Success criteria (all on a stub model):
- [x] A run with `limit=3` on 25 waiting claims works exactly 3 and leaves 22 `waiting`.
- [x] A run on a named claim works only that claim.
- [x] The to-do list is stored by `set_todos` and every item ends `done` or `for_handler`.
- [x] A subagent that raises does not stop the run: the other claims are decided and the run summary names the failure.
- [x] A failed claim returns to `waiting` and is worked again in the same run; a claim that fails twice ends `for_handler`; no claim ends with two decisions or two payments.
- [x] The missed-claim check catches a claim left `waiting` within the cap and works it.
- [x] No claim is left `in_progress` after any run, including one with failures.
- [x] `npm run check:python` is green.

## Phase 5: Dashboard

Builds the queue, claim and instructions pages to the brand in `docs/BRAND.md`. React, TypeScript strict, no `any`.

- Queue page: claims with status, plus the current run's to-do list (todo, in progress, done, for handler), polling while a run is active.
- Claim page: story, items, decision and reasons, steps in order, with a "Read" group listing the sections the agent opened.
- Instructions page: the queue and claim instructions, read only.
- Handler sign-off button for `awaiting_signoff` claims.

Success criteria:
- [x] `npm run check:ts` is green (vitest tests for the to-do list component, the sections-read list and status labels).
- [x] Playwright e2e passes against a seeded backend with a stub-model run: to-do items appear and change status on the queue page; the claim page lists read sections; instructions page shows both instructions.
- [x] In the browser (Playwright MCP), the queue page, a decided claim page and the instructions page look right in light and dark mode: fonts, colors, no one-edge borders.

## Phase 6: Live run, docs and final check

- Update `docs/SPEC.md` (manual moves from "Not for now" into the rules; add `for_handler`), `docs/TECH_STACK.md` (agent, model) and `docs/STATUS.md` (what is built, how to run a capped run).
- Reseed, then run `uv run -m agent --limit 5` with the real model and watch the dashboard.

Success criteria:
- [x] After reseed, a run capped at five on the default model works five claims, the other 20 stay `waiting`, and none is left `in_progress`.
- [x] The dashboard shows the to-do list filling in and being ticked off, and each claim page shows its steps and sections read.
- [x] No handler decision from `data/evals/` was opened or used (I do not open that folder in this build).
- [x] `docs/SPEC.md`, `docs/TECH_STACK.md` and `docs/STATUS.md` match the product.
- [x] `npm run check` is fully green (Python, TypeScript, Playwright, 80% coverage, no thresholds lowered).

## Notes

- Each phase ends with its criteria ticked here, `docs/STATUS.md` updated and a commit (pre-commit hook, never `--no-verify`, never push).
- Not in scope: sign-in, real payments, customer messages, other agent frameworks, anything from later briefs.
