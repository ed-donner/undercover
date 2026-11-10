# Pilot implementation plan

## Scope and approach

Build the claims pilot from `docs/SPEC.md`, starting with the existing health-check skeleton. Use FastAPI and SQLite, LangChain `create_agent` over OpenRouter, and React/Vite with strict TypeScript. Keep the existing check tooling and coverage thresholds.

The backend owns records, workflow transitions, decisions, sign-offs, simulated payments, agent instructions and progress events. The agent reads business data and instructions only through explicit backend API operations. The dashboard uses the same API. Use short background runs and persisted progress events with dashboard polling; durable orchestration, a dispatcher and production hosting are later work.

The six phases below are sequential. Each includes tests and independently verifiable acceptance criteria. During implementation, complete every phase, verify and tick its criteria, update `docs/STATUS.md`, and commit before continuing. This planning change adds no product code.

### Business boundaries

- Seed only `company.json`, `plans.json`, `policies.json`, `customers.json`, `handlers.json`, `claims.json` and `policy_wording.md`, using an explicit allowlist. Do not scan or serve the data directory.
- Do not open or expose `data/evals/`. Do not import held-out claims, security fixtures or the claims manual. Do not expose company settings that encode claims-manual-only rules to the agent.
- Use policy wording alone for coverage decisions. Provide customer history as required by the spec without inventing repeat-claim rules from the manual.
- Separate the decision (`approve`, `decline`, `refer`) from queue status, sign-off and payment. A referral is a completed agent decision, not payment authorization.
- Queue states are `waiting`, `in_progress`, `waiting_for_sign_off` and `decided`. Seed records with `status: open` become `waiting`. An approval above $1,000 waits for sign-off; other completed decisions become `decided`. Show simulated payment status separately.
- The backend, not a prompt or a disabled button, enforces payment restrictions. No real money moves, and there is no sign-in or customer messaging.

## Phase 1 — Persistent records and read API

### Build and rationale

Add a small SQLite repository, typed request/response models and idempotent startup seeding. Use integer cents in storage and exact decimal conversion at API boundaries. Keep the local database out of version control. Tests use isolated temporary databases.

Expose explicit read operations for the queue, full claim, related policy and plan, customer and history, handlers, policy wording and read-only agent instructions. Keep instructions backend-owned and separate from policy wording. Include only the company information the pilot needs, such as currency and the payout approval limit. Every API operation, including the existing health route, has a unique `operation_id`, a one-line docstring and no optional inputs. Avoid generic file-reading or arbitrary database-query endpoints.

### Success criteria

- [x] `GET /api/health` still returns `200` with `{"status":"ok"}`.
- [x] `GET /api/claims` returns exactly the 25 source claims, initially `waiting`, with IDs, customer, type, amount and workflow status suitable for the queue.
- [x] `GET /api/claims/CLM-1001` returns the complete story, items, supporting document text and related record IDs; related read endpoints return the matching policy, plan, customer history and wording version.
- [x] Unknown claim, policy and customer IDs return `404` without changing data.
- [x] Starting twice does not duplicate seeds or overwrite existing workflow data; reopening the database preserves changes.
- [x] Import tests assert that only the named seed sources are accessed and that manual-only company fields are absent from agent-facing responses, without reading evaluation files.
- [x] OpenAPI tests verify unique explicit operation IDs and required inputs for every operation. Agent instructions have a read endpoint and no write endpoint.
- [x] `npm run check:python` passes with the existing coverage threshold.

## Phase 2 — Decisions, sign-off and simulated payment

### Build and rationale

Add explicit command operations for starting a claim, recording a decision, handler sign-off and payment. A decision contains its outcome, payout, calculation, two- or three-sentence explanation and relevant policy section references. Validate the structured data at the backend; keep policy interpretation in the agent rather than duplicating it in hard-coded rules.

Use transactions and conditional state transitions to prevent competing runs or payments. Store a single final decision, sign-off identity and timestamp, and simulated payment record. Declines and referrals have zero payout. Approvals require a positive payout. Reject inconsistent or non-finite amounts and payment amounts that differ from the recorded approved payout. Sign-off takes a known handler ID; without sign-in this is attribution, not authenticated identity.

Payment is a separate operation with an explicit amount. It checks the recorded decision, exact amount, sign-off requirement and existing payment in the same transaction. Use the configured approval limit, not a prompt-provided limit. A sign-off moves an above-limit approval to `decided`; payment remains a separate action.

### Success criteria

- [x] Starting a waiting claim changes its state to `in_progress`; a duplicate or conflicting start returns `409` and creates no second run.
- [x] Decision tests cover approve, decline and refer, persisted reasons/calculation/references, invalid outcomes and invalid amounts.
- [x] An approval for $1,000.00 can be paid without sign-off; an approval for $1,000.01 becomes `waiting_for_sign_off` and direct payment returns `409` with no payment record.
- [x] Signing off with a known handler records the handler and timestamp, changes the queue state to `decided`, and allows a subsequent exact-amount payment. Unknown handlers and sign-off of an ineligible claim are rejected.
- [x] Direct API tests reject payment before decision, payment for decline/referral, mismatched amounts, zero/negative/non-finite amounts and a second payment; none alters the existing financial record.
- [x] A concurrent payment test produces exactly one payment record. Decision replacement and conflicting repeat sign-offs cannot invalidate a completed payment.
- [x] `npm run check:python` passes, including persistence and transition tests.

## Phase 3 — API-only claim agent

### Build and rationale

Replace the health-check demonstration with the single `run(claim_id, thread_id)` entry point, retaining a test-model injection seam. Fetch instructions through the API before constructing `create_agent`. Provide narrowly scoped HTTP tools to read the selected claim and its related records, read policy wording, submit a decision and request payment. Do not provide a sign-off tool, local file tools, evaluation access or arbitrary HTTP tools. Bind mutating tools to the current claim.

Use `openai/gpt-6-luna` with low reasoning effort by default, honoring `MODEL_NAME` when set and `OPENROUTER_API_KEY` from `.env`. Instructions require coverage checks against wording, a transparent payout calculation, policy section references and referral when evidence is insufficient. Explain that approval above the limit is still approval, with payment blocked pending handler sign-off.

### Success criteria

- [x] Stub-model tests demonstrate the complete read-context → decision → payment flow through HTTP tools, without any model-provider requests or real API key.
- [x] Tests cover approve, decline, refer and an above-limit approval whose attempted payment is blocked by the backend.
- [x] Tool tests verify that the current claim cannot mutate another claim and that no tool can sign off, read local records or access arbitrary paths/URLs.
- [x] Tests verify that instructions and claim context come from the API and that the entry point passes the supplied thread ID into the agent invocation.
- [x] Model-construction tests confirm the default model, low default reasoning effort, OpenRouter URL and `MODEL_NAME` override without contacting OpenRouter.
- [x] Missing backend data or a failed tool call cannot silently become a successful decision or payment.
- [x] `npm run check:python` passes with no live-model tests.

## Phase 4 — Run orchestration and observable progress

### Build and rationale

Connect the start operation to a backend-managed background task that invokes the agent without blocking subsequent HTTP requests. Persist a run ID, thread ID, lifecycle and ordered progress events associated with the claim. The dashboard can poll explicit run/event read endpoints. Use a small event bridge so agent-side progress is recorded through the backend API.

Publish concise activity summaries: started, context retrieved, tool invoked, tool completed, decision recorded, payment accepted/blocked and run completed/failed. Show observable actions and the final explanation, not hidden model reasoning, secrets or full sensitive tool payloads.

Keep failure handling small and explicit: a failed run must not leave a claim permanently `in_progress`. Allow a retry only if no decision has been committed; retain failure history. If a decision already exists, preserve its sign-off and payment state. At startup, mark interrupted in-progress runs failed and release undecided claims for retry; do not automatically resume them.

### Success criteria

- [ ] Starting a run returns `202` with run/thread IDs before a controlled stub finishes, and read endpoints remain responsive while it runs.
- [ ] Polling events while a stub run is paused returns already-completed steps; completion adds ordered terminal events and updates the claim state.
- [ ] Repeated/concurrent start requests invoke the agent once for the claim. Different claims retain distinct run/thread histories.
- [ ] Stub failures before decision produce a visible failed run and a retryable claim; failures after decision preserve the recorded decision and payment restrictions.
- [ ] Restart tests preserve decisions, sign-offs, payments and events, and recover interrupted runs according to the stated policy.
- [ ] Progress-event tests confirm that API keys and hidden reasoning are not exposed.
- [ ] `npm run check:python` passes.

## Phase 5 — Handler dashboard

### Build and rationale

Replace the health screen with a queue and a claim-detail workspace. Show all four queue states, customer and claim information, full story/documents, policy and customer history, decision/calculation/reasons/section references, separate payment status and live activity. Provide a process action for waiting claims, a handler selector and sign-off action for eligible approvals, and an explicit simulated payment action after sign-off. Refresh from server responses rather than assuming success.

Add a read-only instructions view. Use Instrument Sans for text, Instrument Serif sparingly for accents and JetBrains Mono for identifiers and figures. Follow the brand's colors, rounded borderless panels, light/dark surfaces and US-dollar formatting. Use plain US English, accessible labels, keyboard navigation, visible focus and text alongside status colors. Include loading, empty, request-error and retry states. Keep the layout usable on narrow screens.

### Success criteria

- [ ] Vitest/Testing Library tests cover queue loading/error/empty states, claim selection and the complete claim-detail content.
- [ ] UI tests cover progress refresh, all decision outcomes, above-limit sign-off, payment success and backend rejection without falsely showing a paid claim.
- [ ] The instructions view displays backend-owned text without edit controls, and a failed run offers retry only when the server permits it.
- [ ] `npm run check:ts` passes with strict TypeScript, no `any`, and the existing 80% coverage thresholds.
- [ ] In a browser via the Playwright MCP server, check the queue, detail, progress, instructions and sign-off/payment interaction at desktop and narrow viewport sizes. Verify readable contrast, full document text, keyboard focus and USD formatting in light and dark modes. Record any unavailable browser tooling as a blocker rather than marking this verified.

## Phase 6 — End-to-end verification and handover

### Build and rationale

Extend Playwright tests to exercise the complete dashboard against a real FastAPI backend and isolated SQLite data, with deterministic stub-agent behavior. Configure that stub only in the test setup, not as a user-accessible production switch. Never depend on a model provider, API spend or evaluator answer keys for automated checks.

Keep root installation, development and check commands working on Windows and macOS. Use `uv run` commands or `.mjs` helpers rather than shell-specific syntax. Update the short README and `docs/STATUS.md` with startup, environment variables, data storage, workflow, tests and the pilot's limits. Do not add an evaluation system or claim measured decision accuracy without authorized evaluation data.

### Success criteria

- [ ] Playwright covers a below-limit approval paid automatically, a decline, a referral and an above-limit approval that remains unpaid until handler sign-off and the separate payment action.
- [ ] End-to-end tests verify full claim content, live steps, read-only instructions, failed-run recovery and persistence after page reload.
- [ ] Each test starts from isolated state and leaves the developer's database untouched; the full suite runs with no OpenRouter key or network calls to a model.
- [ ] `uv sync` and root `npm install` succeed, including hook installation. With the documented environment set, `npm run dev` serves a healthy backend and usable dashboard.
- [ ] `npm run check` exits successfully: ruff formatting/lint, pyright, pytest at 80% or higher coverage, Prettier, ESLint, tsc, Vitest at 80% or higher coverage, and Playwright. Do not lower thresholds, disable rules or exclude files to pass.
- [ ] Browser inspection confirms that a direct unpaid above-limit approval stays blocked even when bypassing disabled UI controls; the UI reflects the backend response.
- [ ] `docs/STATUS.md` and README describe what actually shipped and how to run it. The final implementation commit passes the pre-commit hook; no push is performed.

## Review checkpoint

Plan only. Wait for approval to implement the pilot. No live-model runs, evaluation-file access, infrastructure creation or product implementation are authorized by this plan request.
