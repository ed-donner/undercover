# Pilot plan

## Goal and scope

Build the claims pilot in `docs/SPEC.md`: a handler can view the queue, run the
UnderCover Agent on a claim, follow its progress, read its decision and sign off
an approved payout over $1,000. The agent reads the claim, policy, customer history
and policy wording through the backend API, then approves, declines or refers it
with a payout calculation and a two- or three-sentence explanation citing the
relevant policy sections.

Start from the current FastAPI, agent, React and Playwright skeletons. Use SQLite
for local persistence, LangChain `create_agent` with OpenRouter, and the existing
root development and check commands. Keep the pilot local and simple: one claim
per run, ordinary background execution and polling for progress. Durable agent
execution, batch dispatch and evaluations belong to later builds.

Do not load the claims manual, evaluation files, held-out claims or security test
data. Do not add sign-in, real payments, customer messages or AWS resources. Seed
only explicitly named business files; never scan `data/` recursively. Only the
policy wording supplies coverage rules. Company settings supply the approval
limit, not extra handling rules from the manual.

## Design decisions

- Store seed records, decisions, simulated payments, handler sign-offs, agent
  instructions and run events in SQLite. Seed missing records on startup without
  overwriting work already done. Store money as integer cents or exact decimals
  at boundaries; do not calculate payments with binary floating point.
- Keep coverage decision, queue state and payment state separate. Queue states
  are `waiting`, `in_progress`, `waiting_for_sign_off` and `decided`. Map the seed
  `open` state to `waiting`. A referred claim is decided with outcome `refer`;
  its explanation records what needs human judgment or further information.
- Store an approval and its amount before payment. Approvals over $1,000 wait
  for handler sign-off; smaller approvals can be paid immediately. Payment is a
  separate backend operation taking an explicit amount. The backend compares it
  with the stored approval and checks sign-off in the same transaction that
  records payment. Sign-off names an eligible handler from the seed records; it
  is an attribution mechanism in this pilot without sign-in.
- Reject payment without an approval, payment for a decline or referral, an
  amount mismatch and duplicate payment. Never let a caller bypass the threshold
  by requesting smaller partial payments. Sign-off applies to the stored
  decision and amount; completed decisions are not editable in the pilot.
- Keep instructions in the backend and expose them read only. Give the agent
  narrow HTTP tools for business reads, recording a decision and requesting
  payment. Do not give it a sign-off tool, file access or database access.
- Store timestamped run events for tool activity, results, decisions and errors,
  associated with claim and thread IDs. Show operational progress and the final
  explanation, rather than requesting or displaying private model reasoning.

The endpoint names below are the intended API contract. Each operation will
have a unique `operation_id`, a one-line docstring, typed responses and required
inputs only. Use 404 for missing records, 422 for invalid payloads and 409 for
invalid state transitions or blocked payments.

## Phase 1: Persistent business records and read API

Build the SQLite schema and seed loader, then expose claims, policies, customers,
plans, handlers, policy wording and instructions. This establishes one source of
truth for both the dashboard and the agent. Use an ignored local database file
and temporary databases for tests.

Success criteria:

- [x] Startup seeds `company.json`, `claims.json`, `policies.json`,
  `customers.json`, `plans.json`, `handlers.json` and `policy_wording.md` through
  an explicit allowlist. Tests verify 25 queue claims, valid record relationships
  and initial `waiting` states; the loader never opens excluded files.
- [x] Restarting against the same database preserves changes and creates no
  duplicate records. Tests use isolated databases and leave development data
  untouched.
- [x] `GET /api/health` returns 200 with `{"status":"ok"}`.
  `GET /api/claims` returns the 25 claims with their states and amounts.
- [x] `GET /api/claims/CLM-1001` returns the full story, items and document text;
  `GET /api/policies/POL-2001` and `GET /api/customers/CUS-3001` return the linked
  policy and customer, including previous claims.
- [x] `GET /api/plans`, `/api/handlers`, `/api/policy-wording` and
  `/api/instructions` return their intended records or text. Instructions have
  no public write operation. Unknown record IDs return 404.
- [x] OpenAPI inspection verifies unique operation IDs, one-line route docstrings
  and no optional operation inputs. Backend read and persistence tests pass.

## Phase 2: Decisions, sign-off and simulated payment

Build the workflow before connecting a model. Separate decision submission,
handler sign-off and payment so the approval limit is a backend guarantee.

Success criteria:

- [x] `POST /api/claims/{claim_id}/decision` accepts a validated outcome, explicit
  payout, calculation, explanation, policy references and thread ID for an
  active run. Decline and refer require a zero payout; amounts cannot be
  negative. Invalid outcomes, amounts or missing fields return 422.
- [x] Tests verify approval at $1,000 can proceed without sign-off, while
  $1,000.01 and larger approvals enter `waiting_for_sign_off`. Decline and refer
  enter `decided` without a payment. Approved claims become `decided` after
  simulated payment succeeds.
- [x] `POST /api/claims/{claim_id}/payment`, with a required amount, returns 409
  for an unsigned $1,250 approval and creates no payment record. Tests call the
  endpoint directly, independently of the agent and UI.
- [x] `POST /api/claims/{claim_id}/sign-off`, with a required handler ID, records
  the eligible handler and timestamp. Unknown handlers fail; ineligible handlers
  and claims in the wrong state cannot sign off. The $1,250 payment succeeds
  only after valid sign-off, returning a persisted simulated payment record.
- [x] Tests reject partial amounts, excess amounts, payment before a decision,
  payment for decline or refer, repeated sign-offs, duplicate payments and
  replacement of completed decisions. Concurrent payment requests record at
  most one payment.
- [x] Decisions, sign-offs and payments survive database reopening. The API
  exposes the decision and payment state separately, including who signed off.

## Phase 3: Agent execution and progress API

Replace the hello-world agent with the claims workflow. Preserve the entry point
`run(claim_id, thread_id)` and its stub-model test seam. Keep model-specific
decisions in the agent and workflow enforcement in the backend.

Success criteria:

- [x] The agent fetches its instructions and claim context over HTTP, including
  policy, plan, customer history and policy wording. Tests inspect tool calls
  and supplied context to verify there is no direct file/database access or
  evaluation/manual content.
- [x] Instructions cover policy-based decisions, limits, waiting periods,
  deductions, add-ons and missing evidence. The agent records approve, decline
  or refer, an explicit payout and calculation, and a two- or three-sentence
  explanation with policy section references. No manual-only rules are added.
- [x] Stub-model integration tests exercise approve, decline and refer. An
  approval within the limit is paid through the payment API; an over-limit
  approval remains unpaid awaiting sign-off, including when the stub attempts
  payment anyway.
- [x] Model configuration tests verify `openai/gpt-6-luna` with low reasoning
  effort by default and the `MODEL_NAME` override, including `openrouter/free`.
  All automated tests run without an API key or real model calls.
- [x] `POST /api/claims/{claim_id}/runs`, with a required thread ID, returns 202
  and starts background work without blocking the response. Starting a duplicate
  active run or running a completed claim returns 409; unknown claims return 404.
- [x] `GET /api/claims/{claim_id}/events` returns ordered, timestamped activity
  for the correct claim and thread. Tests observe `in_progress` and tool events
  before the run completes, followed by the persisted decision.
- [x] Model or backend failures produce a visible error event and leave no
  fabricated decision or payment. A failure before decision submission returns
  the claim to `waiting` for an explicit retry. A failure after approval preserves
  it and permits payment retry without rerunning the decision. A backend restart
  marks interrupted runs as failed and releases unfinished claims; it does not
  attempt durable model resumption.

## Phase 4: Queue, claim detail and instructions screens

Build the branded handler workspace on the read and progress APIs. Use the queue
as the entry point, a full claim detail view and a read-only instructions view.

Success criteria:

- [x] The queue displays all 25 claims with ID, customer, summary, amount and
  clearly labeled state. Selecting a claim shows its full story, items,
  supporting documents, policy, plan, add-ons and customer claim history.
- [x] Claim detail displays outcome, payout calculation, explanation, policy
  references, payment state and sign-off details when present. Missing decisions
  are shown as awaiting processing rather than as zero-dollar decisions.
- [x] The instructions view shows exactly the instructions returned by the
  backend and offers no editing controls.
- [x] Loading, empty and failed-request states are understandable. Component
  tests cover these states, navigation and claim content with mocked HTTP calls.
- [x] Browser inspection with the Playwright MCP server verifies queue, detail
  and instructions views at desktop and narrow mobile widths, with keyboard
  navigation, visible focus, readable labels and no horizontal overflow. If the
  MCP server is unavailable, use the repository's Playwright runner and inspect
  its screenshots for the same checks.
- [x] Visual inspection confirms the fonts, colors, rounded panels and plain
  labels in `docs/BRAND.md`. Amounts use US dollar formatting such as $1,250.00;
  status meaning is conveyed with text as well as color.

## Phase 5: Handler actions and live progress

Connect the screens to agent execution and sign-off. Poll the backend while a
claim is active so handlers can see progress without refreshing the page.

Success criteria:

- [x] A handler can start a waiting claim. The UI shows `in_progress`, disables
  duplicate starts and appends tool activity while the stub run is still active.
  On completion it refreshes the decision and queue state; polling stops or is
  cleaned up when the view is left.
- [x] An approved payout over $1,000 displays `waiting_for_sign_off`, its amount
  and an eligible-handler selector. Signing off then requesting simulated
  payment moves it to `decided` and displays the recorded handler and payment.
- [x] Component tests verify actions, polling cleanup and API error handling.
  Failed actions retain the saved claim and provide an explicit retry where
  allowed. A payment failure after sign-off can be retried without a new run.
- [x] Playwright tests with a stub agent and an isolated seeded backend exercise
  a small approval and payment, decline, refer, and over-limit approval followed
  by sign-off and payment. The over-limit case asserts no payment exists before
  sign-off; refreshing preserves the final state.
- [x] Browser inspection verifies progress appears before completion, action
  labels and disabled states are clear, and error/retry behavior is usable.
  End-to-end tests make no OpenRouter requests.

## Phase 6: Full validation and handover

Complete the acceptance checks and document how to run the pilot. Accuracy
against handlers' answer keys is deferred: do not open `data/evals/` for this
build or claim an accuracy score from stub-model tests.

Success criteria:

- [x] `uv sync` and root `npm install` succeed. `npm run dev` starts the backend
  and dashboard, and the queue is usable. Scripts work on Windows and macOS,
  using `uv run` commands or `.mjs` files where scripting is needed; Node 26 and
  Python 3.12 remain the documented targets.
- [x] `npm run check` exits 0: Ruff formatting/lint, Pyright, pytest with at least
  80% coverage, Prettier, ESLint, TypeScript strict checking, Vitest with at least
  80% coverage and Playwright. No thresholds or rules are weakened.
- [x] Review the API schema and test results against every requirement in
  `docs/SPEC.md`, especially API-only agent access, policy references, live
  progress, the read-only instructions and the backend payment barrier.
- [x] `docs/STATUS.md` records the completed features, setup/run/check commands,
  environment variable names, database location and deliberate reset procedure,
  simulated-payment behavior and the pilot's lack of durable agent resumption.
  Keep any added README concise and never include secret values.
- [x] Every phase has its criteria verified and checked off and a status update.
  Implementation commits pass the pre-commit hook (phases 4 and 5 share one
  commit, as noted below). Commit only pilot work, preserve
  unrelated notebook edits and never push or bypass hooks.

## Implementation sequence

Implementation was authorized after review. Build phases in order, add tests with each change,
verify each criterion, update this plan and `docs/STATUS.md`, and commit each
phase as required by `docs/PROCESS.md`. Use synthetic fixtures and stub models
for acceptance testing; no paid model call is needed for the automated checks.

Implementation note: phases 4 and 5 share a dashboard commit after a pre-commit
lint correction overlapped the handler controls. No hook was bypassed.

## Final verification

- `uv sync` and `npm install` completed successfully.
- `npm run dev` served the dashboard on 5173 and returned 25 seeded claims from
  the API on 8000; both servers were stopped after the check.
- Final `npm run check` exited 0: 16 Python tests (99.66% coverage), 11 component
  tests (97.16% statements), five Chromium tests, and all lint/format/type checks.
- Browser screenshots were inspected for queue, claim detail, mobile layout and
  completed sign-off. API tests independently verify the payment barrier,
  concurrent duplicate prevention, persistence and failure recovery.
- No real model calls were made and no evaluation files were opened.
