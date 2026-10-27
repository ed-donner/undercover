# Pilot implementation plan

## Goal and scope

Revise the implemented claims pilot so the UnderCover Agent runs one pass through the waiting queue when the app starts, and runs again when explicitly invoked with `uv run -m agent`. Remove the continuous automatic worker that watches for new waiting claims. Handlers continue to follow progress, inspect decisions and policy references, and sign off approved payouts over $1,000.

The earlier six-phase build and this startup-pass revision are implemented and verified. Database rebuilding, persisted queue order and results, atomic reservation, database ownership, terminal decisions and totals, failure handling, model configuration, HTTP tools, dashboard activity, handler sign-off and payment safeguards are preserved. The follow-up in phases 2, 5 and 6 passes 103 Python tests, 17 component tests, seven Playwright tests and Playwright MCP checks.

For this revision, an app start means backend startup. Each backend start makes one finite pass; refreshing or navigating the dashboard does not start another pass. Once that pass finishes, the backend remains available but does not launch further agent work until the next backend start or an explicit terminal run.

Keep the existing FastAPI, SQLite, LangChain, React, Vite, Tailwind and TypeScript implementation. Use Python 3.12 with uv and Node 26 as specified in `docs/TECH_STACK.md`. The existing claim context, exact monetary amounts, model tools, policy assessment, payment gate and handler actions are the baseline to preserve.

The source queue is `data/claims.json`, currently containing 25 claims. Rebuilding must load every claim in that file, including later additions, with its linked policies and customers. Read only the existing seed allowlist and backend-owned agent instructions. Never import `data/evals/`, `data/security/`, the claims manual or manual-only company rules. Existing initialization continues to preserve stored work; rebuilding is a separate, explicitly invoked operation.

For this pilot, `data/` remains the intake source: changing its files takes effect on a fresh database or an explicit rebuild. Claims added to the stored queue after a processing pass starts remain Waiting until a later startup pass or explicit terminal run. A customer submission screen, live file import, integrations, agent swarms, durable graph execution, sign-in, real payments, customer messages, evaluation scoring and cloud deployment remain outside this revision.

## Design decisions

- **One shared sequential runner.** The startup pass and terminal command reuse the implemented queue selection and execution code. Each pass snapshots the initially waiting claim IDs, processes them in persisted order and ends. Process one claim at a time using the existing `run(claim_id, thread_id)` entry point; the agent continues to read and write exclusively through backend HTTP tools.
- **Stable queue order.** Persist a queue position assigned in `data/claims.json` order. Display and process claims in that order. Backfill existing databases in their current displayed order without altering decisions, sign-offs, payments or activity. Later stored arrivals append to the queue. Sorting by a claim identifier must not silently change queue order.
- **One startup pass, then explicit runs.** After initialization and interrupted-run recovery, snapshot the waiting queue. Begin that finite pass once the backend HTTP API is ready to accept tool calls. End the processing task after every claim in that snapshot has been attempted once. An empty startup queue ends immediately without model calls. There is no idle queue-watching loop, timer or automatic pickup of later arrivals. Keep the removed per-claim Run agent control and start-run endpoint removed.
- **One process owns a database.** The backend, rebuild command and terminal processing command share an exclusive lock for the resolved database path. Refuse a second owner before changing records or making model calls. A process exit releases ownership; an abandoned lock file alone must not block future use. Support the existing default path and `UNDERCOVER_DB_PATH` consistently.
- **Keep ownership after the startup pass.** The backend still serves decision, sign-off and payment operations after processing ends, so it retains database ownership until shutdown. Ending the startup task must not release that ownership prematurely. Stop the app before rebuilding or running the standalone terminal agent, as with the implemented commands.
- **Bounded failure handling.** Attempt a claim at most once per startup or terminal pass. If a run fails before a decision, keep its error activity, return it to Waiting and continue with the remaining claims in the snapshot. Retry only in a later backend startup or explicit terminal invocation. Preserve any decision or payment already committed, including when a later operation fails.
- **Local restart recovery.** Stop claiming new work during shutdown and allow the active attempt a bounded time to finish. On the next start, recover abandoned active runs: retry from the beginning only when no decision exists. Never reassess a decided claim or duplicate a payment. This does not add resumable model execution or support multiple backend workers against one database.
- **Backend owns payment enforcement.** Decisions remain approve, decline or refer. Approval up to and including $1,000 permits simulated payment; approval over $1,000 waits for handler sign-off. Waiting for sign-off must not block processing of subsequent claims. A final decision is not eligible for reassessment until an explicit database rebuild.
- **Keep the model configuration.** Use `OPENROUTER_API_KEY` and the existing `MODEL_NAME` override behavior. Both execution modes use the same model factory, instructions, tools and payment rules. Automated checks use injected stub models and temporary databases, with no external model calls.

### Claim lifecycle

| Trigger | Queue state | Decision and payment |
| --- | --- | --- |
| Initialize or explicitly rebuild a source claim | Waiting | No decision or payment |
| Startup or terminal pass atomically claims the next eligible snapshot row | In progress | One active attempt with a new thread ID |
| Record a decline or referral | Decided | Zero payout; payment unavailable |
| Record an approval up to and including $1,000 | Decided | Approved; eligible for simulated payment |
| Record an approval over $1,000 | Waiting for sign-off | Approved; payment blocked; pass continues with its remaining claims |
| A handler signs off that payout | Decided | Approved; eligible for simulated payment |
| Pay the approved amount | Decided | Exactly one simulated payment recorded |
| Attempt fails before recording a decision | Waiting | Error visible; retry only in a later pass |
| A waiting claim arrives after the pass snapshot | Waiting | No attempt until a later startup or terminal run |
| Startup pass completes | Existing claim states retained | Processing task ends; API and dashboard remain available |
| Rebuild the database explicitly | Waiting for every source claim | Previous decisions, sign-offs, payments, thread IDs and activity removed |

Saving a decision and executing payment remain separate operations. The agent has no sign-off tool. Handler attribution remains unauthenticated in this local pilot. Payment checks apply regardless of who calls the API.

### Terminal commands

Run these commands from the repository root. Stop `npm run dev` with Ctrl+C first; both commands refuse to run against a database owned by an active backend or another command.

```powershell
uv run -m backend.reset_db
uv run -m agent
```

`backend.reset_db` resolves the configured database, validates and loads the seed allowlist into a replacement database, then replaces only the selected database after validation succeeds. It prints the resolved database path and restored claim count. Every source claim is Waiting, and prior decisions, sign-offs, simulated payments, activity and attempt state are cleared. A missing database can be created. Invalid input leaves an existing database intact. The command does not start the agent; all restored claims stay waiting until a processing mode starts. Source files and `.env` are not changed.

`uv run -m agent` is a standalone terminal mode. It starts the required local HTTP backend using the configured backend URL, waits for readiness, processes the waiting claims present at the start of that invocation in persisted queue order, then shuts down its local server. It requires no dashboard or separately running `npm run dev`. It refuses to take over an occupied address or database and gives a useful terminal error. Recovered abandoned attempts without decisions are included in the starting queue; decided claims and approvals awaiting sign-off are skipped.

After each attempt finishes, print the claim ID, recorded outcome, USD payout, explanation, policy references and payment/sign-off state. If an attempt fails, print the failure and any decision already committed, then continue. Flush output as work completes. Finish with attempted and decided counts, the approve/decline/refer breakdown, failed-run count and approvals awaiting sign-off. Decided equals approved plus declined plus referred; a failed run after a saved decision can appear in both the decided and failed-run counts.

Illustrative output using synthetic claims:

```text
TEST-001 APPROVE $100.00 - Simulated payment recorded
Explanation: The documented delay and expense meet the policy conditions. Section 3 covers the hotel cost.
Policy sections: 3, 10
TEST-002 DECLINE $0.00 - No payment
Explanation: The documented loss falls under the stated exclusion. Section 4 excludes this expense.
Policy sections: 4
Attempted: 2 | Decided: 2 | Approved: 1 | Declined: 1 | Referred: 0 | Failed runs: 0 | Awaiting sign-off: 0
```

An empty queue prints zero totals and exits successfully without calling a model. Return exit code 0 when every attempted run completes with a decision, 1 for a setup error or any failed run, and 130 for Ctrl+C. Interruption stops new claims, prints available results and partial totals, and leaves incomplete work recoverable. Neither command performs real payments or grants handler sign-off.

### API surface

Keep existing read, decision, activity, handler sign-off and simulated payment APIs, with their unique operation IDs, one-line docstrings and required inputs. `GET /api/claims` returns persisted queue order. The shared runner reserves snapshot claims through backend-owned transactional code; its agent still accesses context and records outcomes through HTTP tools.

Keep `POST /api/claims/{claim_id}/runs` and its dashboard dependency removed. Queue processing starts once with the backend or through terminal mode. Rebuilding remains a terminal-only operation with no reset HTTP endpoint. No new batch-control API is needed.

## Phase 1: Preserve queue order and coordinate database ownership

Extend the existing storage rather than reseeding an established database. Add persisted queue positions and an atomic operation that reserves the next waiting, undecided, inactive claim. Introduce shared process ownership before startup recovery, execution or rebuilding can modify a database.

Retain this implemented foundation: one ordering and one owner for startup and terminal processing, preventing competing assessments or repeated recorded decisions.

Success criteria:

- [x] `uv run pytest backend/tests/test_seed.py backend/tests/test_queue.py -q` passes using temporary databases and no model calls.
- [x] Fresh initialization assigns positions in source-file order. Synthetic IDs whose lexical order differs from source order prove that API display and worker selection follow the same persisted positions.
- [x] Existing databases migrate in current displayed order without changing saved decisions, exact monetary amounts, sign-offs, payments or events. Repeated initialization preserves both records and positions.
- [x] Concurrent reservation attempts cannot claim the same row, create more than one active assessment, select an already decided claim or skip queue order. Decided and awaiting-sign-off rows do not block later waiting claims.
- [x] A new waiting row appended after the queue has emptied is selectable next. A worker session can exclude its failed attempts without excluding later arrivals.
- [x] Temporary-path ownership tests reject a second backend, command or reset against the same database, permit separate databases, and permit a new owner after a prior process exits unexpectedly.
- [x] `npm run check:python` passes with at least 80% coverage and no relaxed checks.

## Phase 2: Replace continuous processing with one startup pass

Change the implemented backend-managed worker into a finite startup task. Capture eligible waiting claims after initialization and interrupted-run recovery, wait for HTTP readiness, drain that snapshot in queue order, then end the task. Remove the continuous queue polling and pickup of later arrivals. Retain LangChain `create_agent`, existing HTTP tools, `run(claim_id, thread_id)` and responsive API handling.

Reuse the implemented activity, failure handling, restart recovery and test injection seams. Preserve database ownership while the backend remains running, including after the startup pass ends. Keep bounded shutdown behavior for an attempt that is still active. Use one backend process for this pilot; multiple workers and distributed dispatch remain outside scope.

Success criteria:

- [x] Updated lifecycle tests, including `backend/tests/test_worker.py`, pass with scripted models and HTTP clients only.
- [x] A backend started with a temporary queue makes exactly one pass through the initial waiting snapshot after HTTP readiness. At most one claim is active, and attempts follow persisted queue order without a browser or start-run request.
- [x] The startup processing task terminates when its snapshot is exhausted. A claim added during that pass or after it ends remains Waiting while the backend stays running; no idle polling or new model calls occur.
- [x] An initially empty queue ends the startup task without model calls. Adding a waiting claim afterward does not restart processing.
- [x] A scripted approval, decline and referral read required context through HTTP and record the expected outcomes, explanations and references. Eligible payment is recorded exactly once.
- [x] A scripted approval over $1,000 remains awaiting sign-off, blocks attempted payment and allows the next waiting claim to run.
- [x] A failed attempt records its error, returns an undecided claim to Waiting, and allows later claims to finish. It is not retried in the same session. A later session retries it once; an error after a committed decision or payment preserves that record.
- [x] Readiness and shutdown tests preserve the existing safeguards. Finishing the startup pass leaves health, read, handler sign-off and payment APIs available and the database still owned by the backend. Shutdown releases ownership after active work finishes or its process exits.
- [x] A later backend start makes a new snapshot and processes remaining undecided claims once, without reassessing saved decisions or duplicating payments. Browser refreshes and page navigation never trigger runs.
- [x] The removed per-claim start route is absent from OpenAPI; remaining operation IDs, required inputs, thread validation and payment checks still pass their API tests.
- [x] `npm run check:python` passes after the startup-pass changes with at least 80% coverage.

## Phase 3: Rebuild the database from the terminal

Add `backend.reset_db` using the same configuration, source validation and explicit seed allowlist as normal initialization. Build and validate a replacement beside the resolved target, close database handles and replace the target only after success. Hold database ownership throughout the operation and clean up only temporary files created by that invocation.

This gives the student a repeatable fresh queue while preserving ordinary startup's behavior of keeping existing work.

Success criteria:

- [x] `uv run pytest backend/tests/test_reset_db.py -q` covers the command in subprocesses with temporary database paths.
- [x] After synthetic decisions, sign-offs, payments, failures and activity are recorded, `uv run -m backend.reset_db` restores every permitted source claim to Waiting in source order. No old decision, sign-off, payment, active run, thread ID or event remains.
- [x] The command reports the resolved path and source claim count, honors `.env` and `UNDERCOVER_DB_PATH`, creates a missing target and succeeds repeatedly on Windows.
- [x] A synthetic addition to a copied `claims.json`, with valid linked records, appears in the rebuilt queue. Tests derive counts from the permitted source file rather than assuming 25 forever.
- [x] Missing or invalid seed data fails without replacing an existing database. A live owner or competing reset causes a clear nonzero exit without changes.
- [x] File-access tests enforce the seed allowlist without opening evaluation or security files. Only the selected database and owned temporary files can be replaced; business files, secrets and other databases remain intact.
- [x] Rebuilding makes no model calls and starts no queue worker. The restored queue stays waiting until the backend or terminal processing command starts.
- [x] `npm run check:python` passes with at least 80% coverage.

## Phase 4: Work the entire waiting queue from the terminal

Retain the implemented thin `agent/__main__.py` entry point: `uv run -m agent` provides a finite execution mode around the same local HTTP backend, shared runner and configured model. Keep shared queue execution in the backend and the existing `run(claim_id, thread_id)` interface in `agent/main.py`. Preserve readiness, ownership, interruption, reporting and test injection behavior. Production commands must not offer a stub-model selector.

The terminal mode already uses the waiting queue at invocation as its workload, prints each result and final totals, and exits. Preserve that behavior. The revised backend startup pass uses the same finite-workload principle and also does not watch for later arrivals.

Success criteria:

- [x] `uv run pytest agent/tests/test_cli.py -q` passes using subprocesses or an injected terminal entry point, temporary databases and stub models; no test contacts OpenRouter.
- [x] Starting only `uv run -m agent` processes all initially waiting claims in persisted order, one at a time, with no dashboard or separately running backend. Its tools reach the local HTTP APIs, and entry-point tests verify that the package invokes the shared queue worker.
- [x] Captured output prints each decision once, in queue order, including payout, explanation, policy sections and payment/sign-off state. The final totals match persisted records, with correct counts for approvals, declines, referrals, failures and sign-off requirements.
- [x] An empty queue exits 0 with zero totals and no model calls. A second invocation after a successful drain leaves decisions and payments unchanged and prints zero attempted claims.
- [x] A failed claim is attempted once, printed as failed and left recoverable while later claims are processed. Exit code 1 and summary counts accurately cover errors both before and after a decision is saved.
- [x] Missing configuration, an occupied local address or a database already owned by the backend fails clearly before starting an assessment. The command respects the configured database and local backend URL.
- [x] Ctrl+C stops new attempts, prints partial totals, releases process ownership and shuts down the local server. A later invocation recovers abandoned undecided work without repeating committed decisions or payments.
- [x] `npm run check:python` passes with at least 80% coverage.

## Phase 5: Preserve dashboard progress and explain finite processing

Keep the implemented decisions, activity, handler sign-off, simulated payment controls and display polling. Polling refreshes records only and must never trigger agent work. Update waiting-state text so it does not promise continuous automatic pickup: claims outside the startup snapshot wait for another startup or terminal pass. Keep the per-claim Run agent button removed.

Preserve `docs/BRAND.md`, accessible keyboard operation, narrow layouts and light/dark support. Clean up polling on navigation and unmount; recover visibly from request failures. The backend owns processing throughout.

Success criteria:

- [x] `npm run check:ts` passes with strict TypeScript, no `any` and at least 80% Vitest coverage.
- [x] Updated component tests follow startup/terminal assessments through waiting -> in progress -> decided or awaiting sign-off without a start button or start-run request. A later arrival appears as Waiting and does not imply that a worker will pick it up automatically.
- [x] Waiting and failure messages accurately explain the need for another processing pass. Dashboard polling, refreshes and navigation issue no processing requests.
- [x] Selected claims refresh without user actions. Queue ordering, counts, new arrivals, errors, final decisions and payment state are retained.
- [x] Polling tests cover idle gaps, request failure recovery, navigation and unmount without duplicate polling or stale updates.
- [x] Handler sign-off and separate payment remain usable for an approval over $1,000 while the worker assesses subsequent claims. Rejected and duplicate actions show the backend response.
- [x] In Playwright MCP with the scripted backend, follow one startup pass and its decisions, verify later arrivals stay Waiting, and confirm read-only instructions and persisted records after refresh.
- [x] Inspect desktop and 390-pixel-wide layouts in light and dark modes; automatic status text, activity and handler actions remain readable and keyboard accessible without horizontal overflow or uncaught browser errors.

## Phase 6: Verify both execution modes and document the handover

Extend full-stack and terminal integration coverage to the revised workflow. Use separate temporary databases and stub runners for every automated check. Keep the existing payment, exact-money, persistence and data-access regression coverage. Verification leaves the student's working database and model configuration unchanged.

Update the short README and `docs/STATUS.md` to explain one finite pass per backend startup, explicit terminal runs and no continuous queue watcher. Preserve documentation for queue order, database ownership, stopping the app before terminal commands, rebuild's deletion of previous work, output/exit codes, failures and restart limits.

Success criteria:

- [x] `uv sync`, `npm install` and `npm run dev` work on Windows. Health returns `{"status":"ok"}`, and a stub-backed isolated backend starts processing without a browser.
- [x] Full-stack tests verify exactly one startup pass, no processing of later arrivals, an empty startup queue, retry only on a later startup/terminal run, and no browser-triggered assessments. Retain approval/payment, decline, referral, sign-off, the exact $1,000 boundary, blocked/duplicate payment and recovery coverage.
- [x] A terminal integration test rebuilds a temporary database, drains its queue with stubs, verifies every printed decision and summary count against stored results, then proves a repeat drain processes zero claims.
- [x] Rebuilding that temporary database again restores all permitted claims to Waiting and clears prior results. Rebuilding while its backend runs is rejected without modifying the database.
- [x] Repeat the startup-pass handler journey in Playwright MCP: queue -> activity -> decision -> sign-off when required -> simulated payment, with no Run agent action and no unexpected console errors.
- [x] `npm run check` exits 0 after the revision: Ruff, Pyright, pytest, Prettier, ESLint, TypeScript, Vitest and Playwright all pass with the existing coverage thresholds and hooks enabled. All automated models are stubs.
- [x] Inspect the diff for unrelated changes, secrets, databases, course notebooks, evaluation data and later-day features. No student configuration or working database is reset as part of the build.
- [x] README and `docs/STATUS.md` describe the implemented startup-pass behavior and retained terminal commands accurately. Mark changed criteria complete only after verification; report check results and remaining limitations.

## Implementation procedure

The earlier six-phase build was tested, documented and committed, with 101 Python tests, 16 component tests and six Playwright tests passing. Its retained features remain the implementation baseline. The startup-pass revision is now implemented and verified with 103 Python tests, 17 component tests and seven Playwright tests passing, plus a successful production dashboard build.

The implementation changed startup task lifetime and database ownership release, updated dashboard waiting/failure text, and extended regression coverage. The completed foundations and terminal commands in phases 1, 3 and 4 were reused without rebuilding them or removing their safeguards. Changed criteria were checked after verification, run documentation was updated, and each follow-up phase was committed with the pre-commit hook enabled.

Use uv and Windows-compatible commands. Preserve unrelated student changes. Never lower checks, bypass hooks, push commits, create AWS resources or read the evaluation answer key. Run `npm run check` after the final phase and report the result. Live model accuracy remains unmeasured unless a separate evaluation is explicitly requested.
