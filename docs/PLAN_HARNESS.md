# Harness implementation plan

## Scope and starting point

Implement `docs/HARNESS.md` on top of this repository's pilot. This is a plan only: do not change product code, reseed data or call a model until implementation is requested. Leave `docs/PLAN.md` unchanged.

The pilot already has transactional decisions/payments, claim-scoped HTTP tools, persisted activity, background execution and failed-run recovery. In particular, `Workflow.finish()` releases undecided claims and `Workflow.recover()` handles interrupted runs; the brief's description of claims staying stuck does not match this build. Extend those safeguards rather than replacing them.

Planning baseline: `npm run check` passed with 56 Python tests, 19 UI tests and seven Playwright tests. Python and UI statement coverage were 100%. These verify the existing pilot, not any harness acceptance criterion below.

Replace the CLI's Python loop over claims with one queue agent that chooses its work, maintains a persisted to-do list and delegates each claim to a fresh claim agent. Both use LangChain `create_agent`, OpenRouter and backend-owned instructions. Use small tools and middleware in our own agent package, not Deep Agents, the Claude Agent SDK or another agent framework.

### Boundaries and decisions

- Keep FastAPI, SQLite, React/Vite, strict TypeScript and the existing checks. No Supabase, durable graph execution, parallel swarm, evaluation system, sign-in, customer messaging, real payments or AWS resources.
- The backend owns eligibility, caps, attempt budgets, state transitions, document access, audit records and financial safeguards. The queue agent chooses order and delegation; Python does not preselect the first five claims or decide coverage.
- A cap counts distinct claims admitted to a run, including claims that ultimately fail. Retrying an admitted claim does not use another slot. A five-claim run can therefore make up to ten claim attempts, but cannot touch a sixth claim. With fewer eligible claims, process only those available.
- Snapshot eligible claim IDs at run creation to give each local run a finite scope. The agent chooses from that snapshot; claims outside it wait for another run. Eligibility means waiting, undecided and not held for a handler. A named-claim run has a scope and cap of one.
- Permit one active top-level agent run, with one child at a time. Reject competing queue/named starts with `409`; do not introduce a dispatcher or a pool of parallel claim agents. Polling and other API requests remain responsive.
- Keep the four existing queue statuses. Add a persisted `needs_handler` flag and short reason for operational failures; an undecided claim that fails twice stays `waiting` with that flag and is excluded from automatic processing. Show a clear handler label, not an invented coverage decision. Do not let a new run silently reset its failure budget.
- Keep technical failure separate from `refer`, which remains a business decision. An above-limit approval stays approved and awaits sign-off; it is not a failed claim. Preserve the backend's strict $1,000 boundary and separate exact-amount simulated payment operation.
- Use the manual alongside the wording, with the wording as the contract and the manual supplying handling/interpretation rules. Fetch only selected sections, not whole documents in every claim prompt. Do not open `data/evals/`, held-out claims or security fixtures; do not derive prompts or expected answers from them.
- All agent business data, instructions, task writes and activity go through the backend API. Expose no arbitrary file, SQL, URL or handler-sign-off tool. Queue context contains lightweight claim metadata and child summaries, not full customer or medical records.
- Use `deepseek/deepseek-v4.1-flash` with low reasoning effort by default. Preserve `MODEL_NAME` and `OPENROUTER_API_KEY`; do not silently fall back to another model.

The six phases are sequential. During implementation, build tests with each phase, verify and tick its criteria here, update `docs/STATUS.md`, then commit with the pre-commit hook. Never lower thresholds, disable checks, use `--no-verify` or push.

## Phase 1 — Persistent run, task and attempt contracts

### Build and rationale

Extend `backend/models.py`, `backend/store.py` and the workflow layer with top-level agent runs, their scope/cap, ordered to-dos, child-attempt links, failure counts and handler holds. Keep existing claim runs as attempt history, with independent run/thread IDs. Add small dedicated modules rather than growing one workflow class into the whole harness.

Use additive, idempotent SQLite migrations: existing decisions, sign-offs, payments and activity must survive startup without reseeding. Store task states as `todo`, `in_progress`, `done` and `needs_handler`; retain stable task IDs, claim links and ordering. Store the final short run summary and whether completion checks passed.

Use `done` for a decline or paid approval, and `needs_handler` for a referral, an approval awaiting sign-off or an exhausted technical/payment problem. Keep a reason so handlers can distinguish them. Both are terminal for this run; completion with handler work is not the same as an infrastructure failure or successful payment.

Add explicit operations under `/api/agent-runs`: create, read history/current run, read a run and its tasks, update tasks, claim an attempt and finalize a run. Creation accepts a required discriminated request: `{"mode":"queue","max_claims":5}`, `{"mode":"queue","max_claims":null}` for the whole eligible snapshot, or `{"mode":"claim","claim_id":"CLM-1001"}`. Null is explicit, not an omitted optional input. Every operation retains a unique `operation_id`, a one-line docstring and required inputs.

Enforce scope, distinct-claim cap, the two-failure budget and active ownership transactionally at attempt admission. Extend the existing claim-start route with a required parent-run ID and move callers to that contract; do not leave a legacy route that bypasses cap/ownership checks. Task updates cannot erase admitted claims or declare unfinished work complete. Keep decision/payment uniqueness and existing payment rules authoritative.

### Success criteria

- [ ] API tests show valid queue/named creation returns `202` with run/thread IDs before a controlled worker finishes; malformed requests, zero/negative/fractional caps and unknown named claims return `422`/`404` as appropriate.
- [x] Concurrent top-level starts yield one `202` and one `409`; scope/cap/ownership tests reject out-of-scope claims, a sixth distinct claim under cap five and competing attempts without changing records.
- [x] To-do order, all four states, child links, cap usage and final summaries persist across reopening the database. Invalid task transitions and attempts to hide incomplete work are rejected.
- [x] Migration tests open an existing pilot database twice and preserve its financial/activity records; a new database still seeds exactly 25 business claims. No evaluation files are opened.
- [x] Existing single-decision, concurrent-payment and $1,000.00/$1,000.01 sign-off tests remain green. New OpenAPI tests cover required fields and unique operation IDs.
- [x] `npm run check:python` passes at the unchanged coverage threshold.

Phase 1 verification: Python tests, ruff and pyright pass. Creation validation, five-claim cap/retry slots and controlled child-run responsiveness pass; top-level worker scheduling is completed and checked in phase 4. The claim-start API now requires a parent ID; dashboard integration follows in phase 5.

## Phase 2 — Section lookup and auditable document reads

### Build and rationale

Add a backend document service that imports only `data/policy_wording.md` and `data/claims_manual.md`. Split at numbered section headings, retaining document ID, version, section number, title and complete section text, including tables and interpretation notes. A simple deterministic keyword search and section catalog are sufficient for these two short documents; no embeddings, external search or vector database.

Expose required-input catalog/search/read operations with an allowlisted document ID. Search returns section metadata and short excerpts; an explicit read returns a complete section. A child read includes its active attempt ID, allowing the backend to record exactly which document/version/section it delivered on that claim. Searching alone is not recorded as reading a section. Preserve the existing full-wording view for handlers, but remove the claim agent's full-wording tool.

Persist read references in claim activity, and extend decision records with manual version and manual section references alongside policy references. Validate references against the catalog and the attempt's successful reads. Historical pilot decisions remain readable with manual provenance explicitly unavailable, not fabricated. Backfill the document catalog on existing databases without a destructive reset.

### Success criteria

- [x] Catalog tests find all 12 wording sections and 14 manual sections with the correct versions; reading a section preserves its full text and does not return neighboring sections or the complete document.
- [x] Search fixtures find repeat claims, wild animals and meals without receipts; empty/no-match results are explicit, and the catalog lets the agent find a section even when keywords differ.
- [x] Unknown documents/sections return `404`; path traversal and arbitrary paths/URLs are rejected. Seed/access tests extend the allowlist only to the manual, never evaluation or security data.
- [x] A successful read is persisted with claim, child attempt, document, version and section; a failed read/search cannot falsely appear as a successful section read. A terminal or wrong-claim attempt cannot append reads.
- [x] Decision tests reject missing/invalid/unread new references and accept valid wording/manual provenance. Old decisions retain their original fields and render without invented manual citations.
- [x] `npm run check:python` passes, including startup on an already-populated pilot database.

Phase 2 verification: 77 Python tests, 99.80% coverage, ruff and pyright pass. Agent tools now search/read selected sections instead of fetching the whole wording. Historical decisions and exact source text survive reopening; no evaluator data was accessed. UI rendering is checked in phase 5.

## Phase 3 — Fresh claim helpers, instructions and bounded recovery

### Build and rationale

Refactor `agent/main.py` into a reusable claim-helper entry point, retaining `run(claim_id, thread_id)` and the stub-model injection seam. Each attempt constructs a fresh `create_agent` and message state, reads claim instructions from the API and exposes only claim-scoped context, section lookup/read, decision and payment tools. Bind all mutations and document reads to the active attempt. A retry gets a new thread and no previous claim's messages.

Add small LangChain middleware for bounded model-call retries, recoverable tool errors and concise public activity. Keep provider-call retries separate from whole-claim attempts: a short transient model retry does not spend the second claim attempt. Set explicit request timeouts, step limits and an attempt deadline; do not rely on a thread timeout that leaves an unfenced writer running. Expired attempts lose write authority before another begins, including agent payment calls. Handler payment remains a separate operation.

On ambiguous write responses, re-read backend state before retrying. If a decision/payment already committed, reconcile it rather than writing again. An incomplete approved payment may be retried safely against that same decision; if recovery is exhausted, preserve the decision and expose the unpaid issue for a handler. Never release a decided claim as waiting, overwrite it or mislabel an unpaid below-limit approval as successfully paid. Above-limit payment blocking is expected success pending sign-off.

Write separate backend-owned queue and claim instructions from the wording/manual. Claim instructions cover the manual's working sequence, full evidence reading, customer history, referral reasons, payout order and section provenance. Preserve zero payout for referrals; if the manual calls for a provisional payable amount on referral, put it in the explanation/calculation, not an authorized payout. Do not add customer communications or document-request workflows. Update model construction to the new default and low reasoning effort; retain explicit overrides.

### Success criteria

- [ ] Scripted-model tests complete approve/decline/refer/above-limit flows using context plus selected manual/wording sections; no full document is injected automatically and the backend receives the correct provenance.
- [ ] Tests built from synthetic facts and the source rules cover third-claim referral by filing dates, wild-animal interpretation and receipt-free meal calculation. They neither read evaluator answers nor claim to measure model accuracy.
- [ ] Tool isolation tests reject another claim's mutation, expired-attempt writes and sign-off attempts; two child attempts have distinct threads and contain no other claim's messages/evidence.
- [ ] Injected timeout, rate-limit/provider and recoverable tool failures have finite retries. Invalid business requests are not blindly retried, and public errors contain no credentials, hidden reasoning or raw sensitive payloads.
- [ ] Lost-response tests for decision and payment commits retain exactly one decision/payment. A post-decision failure preserves sign-off/payment state; unresolved payment is visibly distinct from successful completion.
- [ ] Model-construction tests assert `deepseek/deepseek-v4.1-flash`, low default reasoning effort, OpenRouter configuration and `MODEL_NAME` override without making a provider call.
- [ ] `npm run check:python` passes using stub models only.

## Phase 4 — Agent-led queue processing and completion checks

### Build and rationale

Add a queue-agent entry point using `create_agent`, separate API-fetched instructions and narrow tools: read eligible queue/scope, write the to-do list, delegate one claim and check/finalize completion. A small custom task middleware/tool bridge persists agent-authored planning before delegation and refreshes task state after tool results. It does not hard-code the claim order or send whole child transcripts back to the parent.

Delegation transactionally starts a child attempt, invokes a fresh helper and returns a one-line result derived from persisted state: claim ID, decision/payout/payment state, or a sanitized failure. Each child step stays attached to that claim. Work sequentially and catch a child's failure at the delegation boundary so other claims can proceed.

On the first pre-decision failure, finish the attempt, release the claim to `waiting` and make it retryable within the same parent run, even when all cap slots have been used. On the second such failure, persist the handler hold, move its to-do to `needs_handler` and continue. Failure counts survive new runs. A technical hold creates no `refer` decision and no payment.

Before reporting completion, use an authoritative backend reconciliation operation. Check unfinished admitted claims, eligible snapshot claims not admitted while slots remain, orphaned in-progress attempts, task/result consistency and payment issues. Reject premature success and return missing work to the agent. A successful check must be persisted before finalization; a finalizer rechecks it transactionally rather than trusting a stale check or a model's closing message.

If the queue agent itself fails, allow one bounded fresh supervisor invocation using persisted tasks/results; never replay committed claim work. If it still cannot proceed, mark the parent failed and release/fence undecided attempts. On backend restart, mark interrupted parent/child runs failed, preserve all committed work, release eligible undecided claims or hold them when their failure budget is exhausted. Do not automatically resume after a process restart; durable orchestration remains later work.

Connect background execution and `agent/cli.py` to one top-level API start followed by polling. Support `uv run -m agent` for the queue, `uv run -m agent --max-claims 5` for a trial and `uv run -m agent CLM-1001` for a named claim. Preserve multiple named IDs as separate explicit named runs if retaining the existing CLI convenience; never implement whole-queue mode as a CLI claim loop. Print the stored short summary and distinguish technical failure from normal referrals/sign-off waits.

### Success criteria

- [ ] A scripted supervisor selects claims in an order different from API queue order, persists its plan, delegates fresh helpers and completes the queue with a short summary verified against stored results.
- [ ] Cap tests cover one, five, fewer-than-cap and uncapped runs. A cap-five run admits exactly five distinct eligible claims; retries do not add slots and all other claims remain untouched and waiting.
- [ ] A first-attempt failure visibly returns to waiting, is retried automatically and can succeed; another claim finishes despite that failure. Two failures produce a persisted handler hold and no third attempt, even in a later run.
- [ ] A scripted supervisor that omits an eligible claim cannot finish successfully: reconciliation returns it, the supervisor processes it within the cap and the final check passes. A supervisor that ignores the check terminates as failed rather than looping indefinitely.
- [ ] Premature prose, false task completion, duplicate delegation and concurrent finalization cannot bypass the backend's completion/cap checks or duplicate a decision/payment.
- [ ] Supervisor-error and backend-restart tests preserve completed work and audit history, release/fence undecided attempts and leave no orphan `in_progress` claim. No restart automatically makes a model call.
- [ ] CLI tests verify a single queue start request, cap/named request bodies, polling, summaries, empty queue, invalid arguments, unreachable backend and exit codes without provider calls.
- [ ] `npm run check:python` passes; requests and activity polling remain responsive while a controlled queue run is paused.

## Phase 5 — Visible queue plan and claim sources

### Build and rationale

Extend the existing dashboard rather than redesigning it. Add queue start controls for the whole eligible queue or a positive claim cap, show the active/latest run, and poll its persisted ordered to-do list, summary and error state. Connect **Process claim** to named mode in the same harness. Disable conflicting starts and reflect backend rejection rather than assuming a start succeeded.

Show text labels for To do, In progress, Done and Left for a handler; link claim tasks to the existing workspace. Distinguish technical handler holds, business referrals and above-limit sign-off. Keep the latest completed run visible after reload; no separate run-history browser is required.

On each claim, show the sections actually read, grouped by attempt with document title, version, section title and expandable complete text. Keep existing evidence, decision, live activity, handler sign-off and separate simulated payment controls. Make the instructions page show separate read-only queue and claim instructions and available source documents.

Use the existing Instrument fonts, brand colors, rounded borderless panels, light/dark surfaces and USD formatting. Include loading, empty, retry and request-error states, keyboard focus and narrow-screen layouts. Do not rely on color alone for task state.

### Success criteria

- [ ] Vitest tests cover queue/capped/named start controls, input validation, conflict/error states and polling; a failed start never displays a fictitious active run.
- [ ] UI tests show persisted ordered tasks progressing through all four states, claim navigation, final summaries and correct state after reload. With no runs, show a clear empty state.
- [ ] Claim tests show exact read section/version references across retries, complete expandable text, old decisions without manual provenance and no cross-claim source leakage.
- [ ] Instructions tests display both backend-owned instruction sets with no edit controls. Handler holds cannot be automatically restarted from the UI; normal sign-off/payment interactions still work.
- [ ] `npm run check:ts` passes with strict TypeScript, no `any` and the existing coverage thresholds.
- [ ] Inspect queue planning, claim sources and instructions through the Playwright MCP server at desktop and narrow sizes in light/dark modes; verify keyboard focus, readable task labels, full text and USD formatting. If that server is unavailable, record the blocker explicitly and perform local Playwright inspection without claiming the MCP criterion passed.

## Phase 6 — End-to-end checks, five-claim trial and handover

### Build and rationale

Extend the isolated `e2e/server.py` harness with deterministic queue and child models, controlled pauses and failure injection. Keep all test controls out of the production application, use temporary databases and never share the developer's database. Migrate existing pilot tests to the new run/document contracts while preserving their financial and workflow coverage.

During implementation, update `docs/SPEC.md` to include the manual and the harness requirements, removing the manual from Not for now. Update `docs/TECH_STACK.md` for queue/claim entry points, scoped section retrieval, middleware and the DeepSeek default. Keep the README and `.env.example` concise and current. Record implementation evidence and remaining limits in `docs/STATUS.md`; leave the pilot plan as historical documentation.

Run the complete automated suite before the live trial. For the required live trial, use a dedicated git-ignored smoke database so existing developer decisions are not destroyed. Stop its backend, run `uv run -m backend.seed` with that database configured, restart the backend/dashboard with the same configuration, then start exactly one `uv run -m agent --max-claims 5`. Use a cross-platform `.mjs` launcher or process environment settings, not POSIX-only environment assignment in package scripts.

Use the actual default model with `MODEL_NAME` unset in the smoke process and an existing OpenRouter key; this makes paid model calls. Observe the dashboard during the run and retain a short result record, not credentials or raw model transcripts. Every subsequent live attempt must also be reseeded first and capped at five. Do not silently substitute a different model or run the whole queue. If credentials, provider/model access or budget permission block the trial, record it as unverified rather than marking it passed.

### Success criteria

- [ ] Playwright covers a five-claim capped run and visible to-do updates, named-claim processing, first-failure retry, twice-failed handler hold, missed-claim recovery and final summary, using stub models only.
- [ ] End-to-end tests verify per-claim source reads and progress, persistence after reload, all decision outcomes, below-limit payment and above-limit payment blocked until handler sign-off. Direct API bypass attempts remain rejected.
- [ ] All automated tests run without an OpenRouter key or provider requests and leave local development records untouched. Production has no test reset/release/failure-injection endpoints.
- [ ] `uv sync` and root `npm install` succeed; `npm run dev` serves the backend and dashboard. Review new scripts for Windows compatibility and use only `uv run` commands or `.mjs` helpers.
- [ ] `npm run check` exits `0`: ruff formatting/lint, pyright, pytest with at least 80% coverage, Prettier, ESLint, strict TypeScript, Vitest with at least 80% coverage and Playwright. No thresholds, rules or coverage scope are weakened.
- [ ] After reseeding the dedicated smoke database, the default-model cap-five run works five distinct claims without manual intervention. Observe tasks filling/completing and per-claim section reads; the other 20 claims remain waiting, with no attempts, decisions or payments. Report any failures or handler holds honestly rather than claiming five successful decisions.
- [ ] Live inspection confirms no duplicate decision/payment and unpaid above-limit approvals remain waiting for sign-off. Record model, cap, run result and observed limits without asserting evaluator-measured decision accuracy.
- [ ] `docs/SPEC.md`, `docs/TECH_STACK.md`, `docs/STATUS.md`, README and `.env.example` describe what actually shipped, including cap/retry semantics, handler holds, manual lookup, costs and no automatic restart resumption. `docs/PLAN.md` is unchanged.
- [ ] Tick only verified criteria, record blockers and report automated/live results separately. Every implementation-phase commit passes its hook; nothing is pushed.

## Review gate

Planning ends here. No product implementation, seed reset or live-model run is part of this planning request. Await approval to implement all six phases.
