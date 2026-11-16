# Plan: the claims pilot

From `docs/SPEC.md`. The pilot gives UnderCover a claims platform: a backend over the records in `data/`, a dashboard for the handlers, and the UnderCover Agent that works the queue by reading each claim and deciding it under the policy wording.

Out of scope, per the spec: the claims manual, sign-in, real payments, messages to customers. The answer key in `data/evals/` is never read by the agent and is not part of this build; checking the agent's accuracy against it comes later.

## Current delivered workflow

The November 11–12, 2026 changes are summarized in [CHANGELOG.md](CHANGELOG.md); [STATUS.md](STATUS.md) describes the current architecture and behavior.

- One Run agent click processes the current waiting queue sequentially. The former single-claim selector and concurrent batch execution are superseded.
- Uncertain claims go to human review, where a handler can approve or deny while retaining the original referral and reviewer record.
- A timed, undecided, unpaid attempt becomes eligible for automatic recovery after two minutes, when no worker is active. There are three attempts total; a third stale attempt is referred to a human instead of running a fourth time.
- Saved decisions/payments and legacy claims without a trustworthy start time are excluded from automatic reruns. The backend continues to enforce over-limit payment sign-off.

The historical phase descriptions and check results below record the build at each stage. Where they describe the old execution or recovery behavior, the current delivered workflow above and the final recovery section take precedence.

## Design

### Claim state machine

A claim moves through six explicit states:

- `waiting` — in the queue, nobody working it
- `in_progress` — the agent is working it
- `waiting_for_sign_off` — the agent approved a payout over $1,000; payment is blocked until a handler signs off
- `waiting_for_human_review` — the agent is facing difficulty to confidently approve or deny a claim or the case is outside the scope of the policies so agent refers to a human to approve or deny.
- `approved` — final approval with payment recorded by the agent or an authorized handler.
- `declined` — the agent or handler denied coverage under the policy, without payment.
Transitions: `waiting` → `in_progress`. A clear decline becomes `declined`; uncertainty becomes `waiting_for_human_review`. A within-limit approval stays `in_progress` until payment makes it `approved`. An over-limit approval waits in `waiting_for_sign_off` until an eligible handler signs off and pays it. Human resolution denies without payment or approves and pays when authorized; an over-limit approval by a reviewer without authority waits for a separate sign-off. The detailed transition table and new verification criteria are in the change-plan section below.

### Backend

FastAPI and SQLite. The database is seeded from `data/` on startup when it is empty: claims, policies, customers, plans, add-ons, handlers and company settings (including the $1,000 `payout_approval_limit`). Never `data/evals/`, `data/security/` or the claims manual. `data/policy_wording.md` and the agent's instructions are files the backend serves; they never need to change.

The database file is `undercover.db` at the repo root (already gitignored as `*.db`), overridable with the `UNDERCOVER_DB` environment variable so tests can seed fresh databases in temporary directories.

Every operation has an `operation_id`, a one-line docstring and no optional inputs. Request bodies are Pydantic models with all fields required.

| Operation | What it does |
|---|---|
| `health` | Check the backend is running (exists) |
| `list_claims` | The queue: claim id, type, summary, customer name, amount claimed, status, decision and payout |
| `get_claim` | One claim in full: story, items, documents, status, decision, payout, reason, policy reference, sign-off and payment |
| `list_steps` | The agent's steps on a claim, in order |
| `run_agent` | Start a timed first attempt on a waiting claim; returns the agent's final reply |
| `rerun_agent` | Retry an eligible stale attempt, or refer it to a human after three attempts |
| `decide_claim` | Record decision (approve, decline, refer), payout, reason and policy reference; sets the status |
| `pay_claim` | Pay an approved claim; takes the amount; blocked over $1,000 without sign-off |
| `sign_off_claim` | An eligible handler signs off an over-limit approval; payment sets the claim approved |
| `refer_human` | Record uncertainty and wait for a human handler, without payment |
| `resolve_human_review` | Record a handler decision, preserving the referral; pay approvals when authorized |
| `add_step` | Record one step of the agent's work on a claim |
| `get_policy` | One policy: plan, add-ons, purchase date, trip, travelers |
| `get_customer` | One customer: contact details and claim history |
| `get_plan` | One plan's limits and deductible |
| `list_add_ons` | The three add-ons and their effects |
| `get_policy_wording` | The policy wording text |
| `get_agent_instructions` | The agent's instructions, read only |

Rules enforced by the backend, not by the prompt: `pay_claim` refuses payment against an approved payout over the approval limit unless the claim has been signed off, refuses a claim that is not approved or is already paid, and refuses to pay more than the approved payout. `decide_claim` refuses a claim that is not in progress or already decided. `sign_off_claim` requires a handler with `can_approve_over_limit` and a claim that is waiting for sign-off. Failures are HTTP errors with a plain-English `detail`, which the agent's tools return to the model as text so it can respond sensibly when a payment is blocked.

The agent's instructions live in `backend/instructions.md`, served by `get_agent_instructions` and read by both the agent and the dashboard, so everyone sees the same text.

### Agent

`agent/main.py` keeps the one entry point `run(claim_id, thread_id)`. On each run it fetches its instructions from the backend API and uses them as the system prompt. It reads everything and acts only through the backend's API, using these tools, each of which records a step on the claim so the team can follow the work:

`get_claim`, `get_policy`, `get_customer`, `get_plan`, `list_add_ons`, `get_policy_wording`, `decide_claim`, `pay_claim`, `refer_human`.

The instructions tell the agent to work like a handler: read the claim, the policy, the customer's claim history, the plan limits, the add-ons and the policy wording; decide approve, decline or refer strictly under the wording; work out the payout by the wording's calculation rules; explain the decision in two or three sentences with the policy section it rests on; and pay an approval itself only when the payout is within the $1,000 limit, leaving larger payouts for a handler's sign-off.

The dashboard triggers the agent through `run_agent` on the backend, which calls `agent.run(claim_id, thread_id)` with the claim id as the thread id.

### Dashboard

React with Vite and TypeScript, hash routes, no router dependency. Brand per `docs/BRAND.md`: Instrument Sans for headings and body, Instrument Serif for the tagline, JetBrains Mono for ids, numbers and money; panels rounded with no outline; light and dark modes via `prefers-color-scheme`. The six claim states use Sea Green (`approved`), Raspberry (`declined`), Marigold (`in_progress`), Coral (`waiting_for_sign_off` and `waiting_for_human_review`) and Cerulean (`waiting`), always with text labels. Raspberry and Cerulean have white text; the others have Midnight text.

- `#/` the queue: every claim with its status, amount and six live count cards and a top Run agent button that automatically processes all waiting claims one by one; refreshed while the agent works.
- `#/claims/{id}` the claim in full: story, items, documents, the customer and policy, the agent's steps as they happen (polled while the claim is in progress), the decision with payout, reason and policy reference, payment, and a sign-off with a handler choice on claims waiting for sign-off and approve or deny buttons on the claims referred to human to decide.
- `#/agent` the agent's instructions, read only

### Testing

Unit tests never call a model: backend tests use FastAPI's `TestClient` against a fresh seeded database; agent tests script a stub model (`GenericFakeChatModel`) through the tool calls, as the skeleton's `agent/tests/test_agent.py` already does. The dashboard is tested with vitest and Testing Library with stubbed `fetch`; Playwright covers the pages end to end, arranging claim state through the backend API where needed.

## Historical pilot implementation

The following pilot and completion phases record the earlier build. Their references to the old status model are historical; the active outcome/referral contract and new checks are in the change plan.

## Phase 1: the backend's database and seed

Build `backend/database.py` (SQLite connection, schema, `UNDERCOVER_DB` override) and `backend/seed.py` (load `data/` into an empty database: 25 claims, 50 policies, 49 customers, 3 plans, 3 add-ons, 3 handlers, company settings). Seed on startup when the database is empty. Add `undercover.db` handling to `.gitignore` (already covered by `*.db`).

- [x] `uv run pytest backend/tests` passes with tests asserting the seeded counts, the company's `payout_approval_limit` of 1000, and that each claims row keeps its items and documents as JSON
- [x] A test asserts the seed never reads `data/evals/`, `data/security/` or `claims_manual.md` (the seed only opens the seven seed files)
- [x] Starting the backend twice does not duplicate data: `uv run -m uvicorn backend.main:app`, then `curl http://127.0.0.1:8000/api/health` twice, still one set of claims in the database
- [x] `uv run ruff format --check`, `uv run ruff check` and `uv run pyright` pass

## Phase 2: the backend's read API

Operations `list_claims`, `get_claim`, `list_steps`, `get_policy`, `get_customer`, `get_plan`, `list_add_ons`, `get_policy_wording` and `get_agent_instructions`, each with an `operation_id`, a one-line docstring and no optional inputs. `backend/instructions.md` holds the agent's instructions.

- [x] `curl http://127.0.0.1:8000/api/claims` returns 25 claims with `status: "waiting"`, ids from CLM-1001 to CLM-1025
- [x] `curl http://127.0.0.1:8000/api/claims/CLM-1001` returns the full claim: story, three items, documents, `policy_id: "POL-2001"`
- [x] `curl http://127.0.0.1:8000/api/policies/POL-2001`, `/api/customers/CUS-3001`, `/api/plans/premium`, `/api/add-ons`, `/api/policy-wording` and `/api/agent-instructions` each return their record, and the wording matches `data/policy_wording.md`
- [x] `get_claim` on an unknown claim returns 404; tests cover every read operation, including empty steps on an unworked claim
- [x] `npm run check:python` passes, with backend coverage at 80% or more

## Phase 3: the claim lifecycle

Operations `add_step`, `decide_claim`, `pay_claim`,`refer_human`, and `sign_off_claim`, with the money rules enforced in the backend. Status transitions: `decide_claim` sets `declined`, `waiting_for_human_review` or an `approved` within the limit, and `waiting_for_sign_off` for an approval over the limit. `pay_claim` pays an approved claim within its payout, blocked over the approval limit unless signed off. `sign_off_claim` records the handler, pays the approved payout and sets `approved`. `waiting_for_human_review` records the handler and pays the payout if handler approves then sets `approved` or if handler denies sets `declined` and in which case no payout is done.

- [x] Tests: deciding CLM-1001 as approve with payout 420 records decision, reason, reference and `decided_on`, and the status becomes `approved`
- [x] Tests: deciding with payout 2000 sets `waiting_for_sign_off`, and `pay_claim` of 2000 returns an error whose `detail` says the payout needs a handler's sign-off
- [x] Tests: after `sign_off_claim` with a handler who `can_approve_over_limit`, the claim is `approved` with `paid_amount` 2000, `signed_off_by` and `paid_on` set
- [x] Tests: `pay_claim` refuses a claim that is not approved, an amount over the approved payout, a claim already paid, and a handler without `can_approve_over_limit` signing off; `decide_claim` refuses a claim that is already decided, so a test can arrange a claim without calling a model
- [x] Tests: setting `waiting_for_human_review` initiates having approve or deny buttons and upon approve the status is `approved` and payout is done and deny sets the status as `declined` and no payout is done.
- [x] Tests: `add_step` then `list_steps` returns the steps in order
- [x] `npm run check:python` passes with coverage at 80% or more

## Phase 4: the agent and its instructions

Rewrite `agent/main.py`: fetch the instructions from `get_agent_instructions` and use them as the system prompt; the eight tools over the backend API, each recording a step on the claim; tool errors returned to the model as text. Write `backend/instructions.md` to the design above: work like a handler, decide under the policy wording alone, calculate payouts by its rules, explain in two or three sentences with the policy section, pay within the limit and leave larger payouts for sign-off. Add `run_agent` to the backend, which sets the claim `in_progress`, calls `agent.run(claim_id, claim_id)` and returns the reply.

- [x] Tests with a stub model scripting the tool calls: the agent reads a claim, policy, customer, plan, add-ons and wording, decides approve with payout 420 and pays; the claim ends `decided` and paid, and `list_steps` shows the steps in order
- [x] Tests with a stub model: an approval of 2000 leaves the claim `waiting_for_sign_off`, and the blocked `pay_claim` returns the sign-off message to the model
- [x] Tests: `run_agent` on a waiting claim returns the agent's reply; running it on a claim that is not waiting returns an error
- [x] `npm run check:python` passes with coverage at 80% or more
- [x] Live check with `OPENROUTER_API_KEY` set: run the agent on CLM-1001 through the run operation on a running backend, then `curl http://127.0.0.1:8000/api/claims/CLM-1001` shows a decision with a reason and a policy reference, and the claim is decided and paid (approved at $420, referencing sections 3, 10 and 12); running it from the queue is checked in the browser in Phase 5

## Phase 5: the dashboard's queue

The queue page with the brand: layout, fonts and colors from `docs/BRAND.md`, light and dark modes, status chips in the four state colors, money in JetBrains Mono as `$1,250.00`, and a Run agent button on waiting claims that calls `run_agent` and refreshes the queue while the agent works. Hash routes for queue, claim and instructions pages. A typed API client in `src/lib/api.ts`.

- [x] `npm run check:ts` passes with vitest coverage at 80% statements or more, testing the queue with a stubbed `fetch`: 25 claims, statuses, amounts, the run button on waiting claims and its absence on decided claims
- [x] With `npm run dev`, the Playwright MCP server sees the queue at `http://localhost:5173` with 25 claims, each with a status chip, in both light and dark mode
- [x] An e2e test covers the queue: claims listed with their statuses, and a claim detail route opens
- [x] The existing health e2e test still passes

## Phase 6: the claim detail and instructions pages, and the end-to-end run

The claim page: story, items and documents, the customer and policy, the agent's steps polled while the claim is in progress, the decision panel with payout, reason and policy reference, payment, and sign-off with a handler choice on claims waiting for it. The instructions page renders the agent's instructions read only. Finish `docs/STATUS.md`.

- [x] `npm run check:ts` passes with vitest coverage at 80% statements or more, covering the claim page with stubbed `fetch` (decision, steps, sign-off button when waiting for sign-off) and the instructions page
- [x] With isolated backend/Vite test servers, Playwright Chromium (substituting for the unavailable MCP server): open a claim, see the story, items and documents; open the agent instructions, read only
- [x] An e2e test decides a claim over $1,000 through the backend API, then signs off on the claim page and sees the claim decided and paid
- [x] An e2e test runs the pages in dark mode
- [x] `npm run check` passes in full: ruff, pyright, pytest, prettier, eslint, tsc, vitest and Playwright
- [x] `docs/STATUS.md` describes the whole build, how to run it and any known gaps

## Next steps after the current-code review (November 11, 2026)

This is a completion plan for the pilot, preserving the original phases above. No later build brief is present in `docs/`, so the next work stays within the pilot. The student approved implementation, and all completion phases below are verified.

### Review baseline

`docs/STATUS.md` says Phase 6 is pending, but the working tree already contains the claim detail and instructions pages, their unit tests, and sign-off and dark-mode end-to-end tests. Review and finish these changes rather than rebuild them. Existing edits also include notebooks and `docs/CODE_STANDARDS.md`; preserve those and keep unrelated edits out of product commits.

`npm run check` passed during this review: 45 Python tests (99.67% coverage), 19 dashboard tests (93.96% statement coverage), and 5 Playwright tests. ESLint reported one warning for a conditional in `e2e/claim.spec.ts`. Passing checks do not yet cover the gaps below. Playwright can reuse running servers, so this result alone does not establish isolation from the local development database. No model calls or answer-key inspection were needed.

### Completion phase 1: enforce the claim lifecycle and sign-off rule

The backend currently allows a decision on a waiting claim, despite the original design requiring `in_progress`. It also checks the requested payment amount against the sign-off limit: an approval for $2,000 can be paid $1,000 without sign-off and become `decided`. Base the sign-off requirement on the approved payout so smaller payment requests cannot bypass it. Reject negative and non-finite money inputs, keeping payment separate from the decision.

- [x] Add regression tests showing a waiting claim cannot be decided, an in-progress claim can be decided, and a decided claim cannot be decided again.
- [x] Add a regression test: approve $2,000, request payment of $1,000 without sign-off, receive an error, and retain `waiting_for_sign_off` with no payment recorded.
- [x] Verify the boundary: a $1,000 approval can be paid without sign-off; an approval above $1,000 requires sign-off; authorized sign-off pays the approved payout exactly once.
- [x] Money validation rejects negative and non-finite values without changing the claim. Keep zero-payout declines and referrals valid.
- [x] Update lifecycle and stub-agent test setup to enter `in_progress` without calling a real model; `npm run check:python` passes with coverage at least 80%.

### Completion phase 2: finish the claim page's decision and loading behavior

`DecisionPanel` currently labels every unpaid decision as waiting for sign-off, including declines and referrals. Show payment and sign-off information according to the decision and status. The page also silently converts failed customer/policy loads into permanent loading placeholders and failed step loads into an empty history. Show useful errors for these required sections. Clear previous claim state on navigation and ignore responses for a claim that is no longer selected.

- [x] Tests cover approve, decline and refer: only an approval waiting for sign-off displays the sign-off message and controls; an unpaid approval within the limit has an accurate payment label.
- [x] Tests cover sign-off failure, disabled submission while signing, and exclusion of handlers without approval authority.
- [x] Tests show customer, policy, steps and handler load failures visibly, without suggesting that missing results are still loading or that the history is empty.
- [x] A delayed-response test navigates between claim ids and verifies that the earlier response cannot overwrite the selected claim.
- [x] Timer-based tests verify that steps refresh during `in_progress`, the completed decision appears, and polling stops when the claim finishes or the page unmounts. Repeated step descriptions render without duplicate React keys.
- [x] Add the brief function comments required by `docs/CODE_STANDARDS.md` to the new page functions; `npm run check:ts` passes with coverage at least 80%.

### Completion phase 3: make end-to-end verification repeatable

The sign-off test currently chooses any waiting claim and changes it, while Playwright is configured to reuse an existing backend. Give the suite a dedicated database and servers, and arrange known claim states without a live model. Update the sign-off setup to respect the lifecycle rule from completion phase 1.

- [x] Automated tests cannot reuse the ordinary development backend or change its database; use dedicated test ports and an isolated test database with deterministic setup.
- [x] Replace the conditional early return in `e2e/claim.spec.ts` with deterministic setup and assertions; ESLint reports no warnings for this test.
- [x] The sign-off journey verifies an over-limit approval, eligible handler selection, payment, recorded signer, and removal of sign-off controls.
- [x] Add a browser test for read-only agent instructions and assert story, item and document content on the claim page.
- [x] `npm run e2e` passes on two consecutive runs without manual database cleanup or paid model calls.

### Completion phase 4: inspect the pages in the browser

Automated assertions cover behavior, but the original Phase 6 browser review remains outstanding. Use the Playwright MCP server when available; otherwise record the browser-tool substitution used for visual review.

- [x] Inspect queue, claim detail and instructions in light and dark mode, including a narrow viewport; content, tables and sign-off controls remain readable and usable.
- [x] Check keyboard navigation and visible focus for links, handler selection and sign-off.
- [x] Inspect waiting, in-progress, waiting-for-sign-off, approved-and-paid, declined and referred claims using test fixtures; the visible labels match each state.
- [x] Record the outcome and resolve any layout or usability defects before marking the original Phase 6 browser criterion complete.


Browser review evidence: Playwright Chromium generated screenshots in `e2e/test-results/`, inspected directly because a Playwright MCP server was unavailable. All three pages were reviewed at 1440px and 390px in light and dark mode; all six claim states and mobile sign-off were checked. Fixed wrapped money/headings, narrow table overflow, navigation/control wrapping, and keyboard focus. The expanded browser suite passes all 11 tests.

### Completion phase 5: reconcile documentation and hand over the pilot

Update the documentation to describe the verified product and any remaining limitations. Keep future harness, database migration and deployment work out of this pilot completion.

- [x] `docs/STATUS.md` describes all three dashboard routes, the backend and agent architecture, payment/sign-off enforcement, run commands and known limitations. Assess and document the current behavior where a failed agent run can leave a claim `in_progress`; do not claim retry or recovery exists.
- [x] Tick the original Phase 6 criteria only when their corresponding checks and browser review are complete.
- [x] Run `npm run check` after the final product changes; all checks pass without lowering thresholds or disabling rules.
- [x] Commit each completed implementation phase with the pre-commit hook enabled, staging only its intended files and preserving unrelated student work. Do not push.

Final verification: `npm run check` passed with 58 Python tests (99.67% coverage), 31 dashboard tests (96.38% statement coverage), and 11 Playwright tests. Format, lint and type checks passed without lint warnings. Each completion phase was committed with hooks enabled; unrelated notebook and code-standard edits were preserved, and nothing was pushed. The failed-run limitation is documented and covered by a regression test.

## Change plan: explicit outcomes and human review

This section implements the student's revised requirements. It supersedes conflicting status and referral behavior in the earlier design; earlier checked boxes record the previous pilot build, not completion of these changes. The student authorized implementation; verified criteria are checked below.

### Baseline before this change

The backend uses `decided` for approved, declined and referred claims. The agent already knows to refer ambiguous claims through `decide_claim(decision="refer")`, but that records a terminal decision. There is no referral endpoint, handler decision endpoint, reviewer audit record or review form. The dashboard's types, chips, fixtures and browser tests all assume the old statuses. Existing SQLite databases retain their records across startup, so changing the seed alone would leave old claims incompatible with the new dashboard.

### Proposed behavior and terminology

Use the six status values in the revised design: `waiting`, `in_progress`, `waiting_for_sign_off`, `waiting_for_human_review`, `approved`, `declined`. Use Approved and Declined as outcome labels, with Approve and Deny as the human action buttons. Keep `approve` and `decline` as decision values to avoid unnecessary changes to tools and historical records. There is no new `denied` status alias.

The revised definition of `approved` includes payment. Keep approval and payment as separate operations, as required by the tech stack: an agent's within-limit approval records `decision="approve"` while status remains `in_progress`; successful payment changes status to `approved`. Until then the detail page says Approval recorded, payment pending. This avoids presenting a claim as paid before payment succeeds and lets existing active-claim polling observe the payment. An over-limit approval enters `waiting_for_sign_off`; authorized sign-off pays it and changes status to `approved`. If a run fails between approval and payment, retain the recorded decision and show payment pending; this change does not introduce automatic recovery.

| Current state | Action | Result |
|---|---|---|
| `waiting` | Run agent | `in_progress` |
| `in_progress` | Agent approves $1,000 or less | Approval recorded; remains `in_progress` until payment |
| `in_progress` with recorded approval | Pay approved amount | `approved`, payment recorded |
| `in_progress` | Agent approves above $1,000 | `waiting_for_sign_off`, unpaid |
| `in_progress` | Agent denies under clear policy terms | `declined`, unpaid |
| `in_progress` | Agent cannot confidently settle the claim | `waiting_for_human_review`, unpaid |
| `waiting_for_human_review` | Handler denies with reasons | `declined`, reviewer recorded, unpaid |
| `waiting_for_human_review` | Handler approves $1,000 or less | `approved`, reviewer and payment recorded together |
| `waiting_for_human_review` | Handler with over-limit authority approves above $1,000 | `approved`, reviewer, sign-off and payment recorded together |
| `waiting_for_human_review` | Handler without over-limit authority approves above $1,000 | `waiting_for_sign_off`, reviewer recorded, unpaid |
| `waiting_for_sign_off` | Eligible handler signs off | `approved`, sign-off and payment recorded |

Human review and payout sign-off are separate responsibilities. Any existing handler may review coverage; only handlers with `can_approve_over_limit` may authorize payment above $1,000. The backend enforces that distinction regardless of dashboard controls. A referral waits for a real handler action; the agent does not simulate or automatically complete that action. As with the current pilot, selecting a handler records attribution but is not authenticated identity.

Refer when essential documents are missing, evidence conflicts, wording is ambiguous or the case cannot be confidently resolved from the supplied policy. Clear exclusions or clearly uncovered losses can still be declined with the relevant policy reference. Explain what is uncertain and what the handler needs to resolve; do not invent a policy section or force approval because the agent is uncertain. No numeric confidence score, claims-manual access, new model or later-course harness is needed.

### API and record changes

- Add `POST /api/claims/{claim_id}/refer`, operation id `refer_human`, with required `reason` and `reference`. It accepts only an undecided `in_progress` claim, records the referral and an activity step, sets `decision="refer"`, and moves to `waiting_for_human_review` without paying. For a missing applicable section, `reference` may explicitly say that applicability is unclear. Require nonblank explanatory text.
- Preserve existing `decide_claim(decision="refer", payout=0, ...)` calls by routing them through the same referral logic; reject a nonzero referral payout. The agent's new normal route is the explicit `refer_human` tool. Approval/decline validation still prevents overwriting a recorded decision; a referral can only be resolved through the handler operation.
- Add `POST /api/claims/{claim_id}/human-review`, operation id `resolve_human_review`, with required `handler_id`, `decision` (`approve` or `decline`), `payout`, `reason` and `reference`. This operation is used by the dashboard and is not an agent tool. It accepts only `waiting_for_human_review`, validates the handler, and applies the transition table above. A denial requires payout zero; approvals require finite nonnegative amounts. Nonzero denial payouts are also rejected by the ordinary decision endpoint.
- Add nullable `referral_reason`, `referral_reference`, `referred_on`, `reviewed_by`, and `reviewed_on` fields to claims. Preserve the referral explanation after a human decision replaces the current `decision`, `reason`, `reference`, `payout` and `decided_on`. A pending referral has no final decision timestamp. Read APIs return the new fields; the queue already returns the status and needs no new route.
- Reuse backend payment/sign-off validation inside the human-resolution transaction. Keep payment as a distinct operation for the agent. Human resolution can orchestrate decision and payment together, as existing sign-off already does. Do not make loopback HTTP calls from one backend operation to another.
- Require the expected status in conditional updates and check affected rows so competing/repeated review submissions cannot overwrite a decision or pay twice. Commit decision, reviewer, payment/sign-off and activity step together. Failed validation changes none of them.

### Phase 1: introduce the status contract and migrate stored claims

Update `backend/database.py`, startup initialization and lifecycle status assignments, with migration tests. Make fresh and existing databases agree before adding review actions. Use a small versioned or idempotent SQLite migration, not a database reset.

Legacy mapping: `decided` + paid approval → `approved`; `decided` + unpaid approval within limit → `in_progress` with the recorded decision retained; an unpaid over-limit approval without sign-off → `waiting_for_sign_off`; `decided` + decline → `declined`; `decided` + refer → `waiting_for_human_review`. Copy legacy referral reason/reference/date into the new referral fields before clearing its final-decision timestamp. Preserve existing waiting, running and sign-off claims. Do not infer a missing reviewer or signer. Report an inconsistent legacy row that cannot be mapped rather than deleting it or inventing an outcome.

- [x] Tests construct an old-schema temporary database containing paid approvals, unpaid approvals, declines, referrals and waiting/sign-off claims; startup adds fields and maps every supported case as specified.
- [x] Running migration twice changes nothing on the second run; all claim ids, amounts, documents, payment/sign-off records, activity steps and seed counts are preserved.
- [x] New decisions/payments/sign-offs return the new statuses; no live API response uses `decided`. A within-limit recorded approval stays in progress until payment succeeds.
- [x] Existing money, duplicate-decision, duplicate-payment and $1,000-boundary regression tests pass with updated expectations; `npm run check:python` passes at 80% coverage or more.

### Phase 2: implement referral and handler resolution

Add the request schemas, shared lifecycle helpers and two operations in `backend/main.py`. Preserve the original referral explanation independently of the handler's final reason. Keep both writes and payments transactional.

- [x] API tests: refer a running claim → `waiting_for_human_review`, referral explanation/date and activity step saved, no payment; equivalent legacy `decide_claim(... refer ...)` produces the same result.
- [x] API tests: a handler's $420 approval resolves the referral as `approved` and paid; denial resolves it as `declined` with payout zero and no payment. Both record reviewer, final reason/reference and decision date while retaining referral details.
- [x] API tests: an authorized handler's $2,000 approval records sign-off and pays; an unauthorized handler's $2,000 approval waits for sign-off, and smaller payment attempts still cannot bypass that requirement.
- [x] Tests reject unknown claims/handlers, wrong-state actions, repeated or competing resolutions, nonzero denial/referral payouts, blank explanations and negative/non-finite amounts without partial updates or duplicate activity/payment records.
- [x] OpenAPI lists both new operation ids and required inputs; `npm run check:python` passes with coverage at least 80%.

### Phase 3: teach the agent to hand off uncertain cases

Add the API-only `refer_human` tool in `agent/main.py` and clarify `backend/instructions.md`. Keep clear approvals and exclusions automatic; hand off genuine uncertainty with an actionable explanation. Once referred, end the run with a concise handoff message and do not pay or attempt the handler endpoint.

- [x] Stub-model tests cover missing required evidence, conflicting evidence and ambiguous policy applicability: the referral tool is exposed, reaches the backend, records a step, and leaves the claim waiting for human review without payment.
- [x] Stub tests verify a clear approval is paid and becomes `approved`, an over-limit approval waits for sign-off, and a clear exclusion becomes `declined` without referral.
- [x] A test inspects the tool list and confirms `resolve_human_review` is not exposed to the agent; referral failures return useful backend error text to the model.
- [x] Instructions explain how to separate clear lack of coverage from unresolved policy applicability, and prohibit inventing evidence or policy references. Automated tests make no real model calls; `npm run check:python` passes.

### Phase 4: show outcomes and give handlers a review form

Update `dashboard/src/lib/api.ts`, status labels/chips and CSS, queue fixtures, and the claim detail page. Use Approved (Sea Green), Declined (Raspberry), Waiting for human review (Coral), Waiting for sign-off (Coral), In progress (Marigold), and Waiting (Cerulean), always with text labels. Show the referral reason separately from the final human decision.

On a referred claim show a Handler selector, payout input in USD, reason and policy-reference fields, and Approve/Deny buttons. The form supplies zero payout for Deny. Show an explanatory message when an approval above $1,000 will need another handler's sign-off. Disable both actions during submission, show API validation errors, and refresh the claim after success. Only referred claims show review controls; existing sign-off controls remain for sign-off claims. Poll both waiting-for-review and waiting-for-sign-off claims so another handler's action appears and closes stale controls; stop at final outcomes and cancel on navigation.

The revised queue paragraph also moves Run agent to the top. Proposed scope is one selected waiting claim: add a claim selector and top Run agent button using the existing single-claim endpoint, disabled when nothing is eligible or a run is pending. Do not infer a dispatcher or batch execution from button placement. Implementation uses one selected waiting claim, as proposed and stated at the start of the build.

- [x] Vitest covers all six status labels/chips with no Decided label, paid approvals, recorded approvals awaiting payment, and readable pending referrals.
- [x] Form tests cover approval, denial, missing inputs, invalid amounts, handler selection, API failure, disabled double submission and the over-limit sign-off path; the original referral reason remains visible after resolution.
- [x] Tests verify review and sign-off polling observes another handler's resolution and stops afterward; navigation ignores stale responses and failed review requests leave controls recoverable.
- [x] Queue tests cover the agreed top-button behavior, waiting-only eligibility and existing run errors without adding batch processing unless explicitly selected.
- [x] `npm run check:ts` passes with strict types and at least 80% statement coverage; old fixtures and App tests use the new status contract.

### Phase 5: verify journeys and reconcile documentation

Extend the isolated Playwright fixtures and browser suite. Reconcile the active design at the top of this document, the changed acceptance criteria and `docs/STATUS.md`. Update the status paragraph in `docs/SPEC.md` to reflect the student's approved requirement, retaining the original policy/payment rules. Keep previous build verification clearly historical; checked boxes are not evidence for an unimplemented requirement.

- [x] Browser journeys: referral → handler approval → approved and paid; referral → handler denial → declined and unpaid; over-limit human approval without authority → sign-off → approved and paid; direct agent approval/decline continue working using stubbed/prepared records.
- [x] Browser assertions verify queue and detail show the same outcome, reviewer and payment amounts are correct, referral reasons survive, and stale review controls disappear after resolution. Tests do not mutate the development database or call a model.
- [x] Inspect updated queue chips and review/sign-off forms in light/dark mode at desktop and phone widths; check keyboard navigation, visible focus, error messages and long referral explanations using Playwright MCP if available, or record the browser substitution used.
- [x] `npm run check` passes in full without lowering thresholds or disabling rules. Repeat the isolated browser suite to confirm clean setup.
- [x] Update `docs/STATUS.md` with migration behavior, endpoints, six statuses, human-review/sign-off distinctions, tests and remaining limitations. In particular, there is still no sign-in, authenticated reviewer identity, durable graph or automatic failed-run recovery.
- [x] Implement and commit each phase with hooks enabled, preserving unrelated student edits; never push. Check off this section only after its new criteria are verified.

Implementation handoff: the five phases were implemented in order. Migration was verified on temporary legacy databases, and browser journeys use disposable records without model calls. Existing development records upgrade on their next backend database connection. No later course build is included.

Outcome/review verification: `npm run check` passed with 89 Python tests (99.30% coverage), 47 dashboard tests (96.12% statement coverage), and 21 browser tests. The expanded browser suite passed on two consecutive clean setups. Playwright Chromium screenshots were inspected directly because no Playwright MCP server is available: queue, review errors and controls, long referral explanations and sign-off focus are readable in light/dark mode at 1440px and 390px. All five phases were committed with hooks enabled; unrelated student edits were preserved and nothing was pushed.

## Batch run and queue totals update

The student requested this implementation directly. It supersedes the earlier single-claim selector. Run agent fetches the current queue, starts every waiting claim concurrently through the existing run API, waits for all results, and reports failures by claim without cancelling other runs. The button prevents another batch while these runs are pending. Each backend start conditionally claims a waiting record so two dashboards cannot run it twice. No model or tool architecture changes are required.

Six large responsive cards precede the queue: Total claims, Waiting claims, Approved claims, Denied claims, Referred to human, and Waiting to sign off. Counts use current statuses from the same polled records as the table. Denied maps to declined; referred and sign-off counts represent currently pending claims. In-progress claims contribute to total but have no separate card, matching the requested six cards. A dash is shown before records load.

Verification includes concurrent starts before any completion, waiting-only selection from a fresh snapshot, partial failures, duplicate clicks/competing dashboards, empty/loading counts and live count updates. The browser batch test intercepts run requests so it never calls a real model. Desktop/phone screenshots in both themes verify the cards.

Batch/totals verification passed: `npm run check` reports 90 Python tests (99.31% coverage), 52 dashboard tests (95.36% statements), and 22 browser tests. Queue screenshots were inspected at 1440px and 390px in light and dark mode using Playwright Chromium in place of the unavailable MCP server. All six cards fit and remain legible.

## Sequential queue processing correction

After errors during simultaneous runs, the student requested automatic one-at-a-time processing. This supersedes concurrent batch execution above: one click reads the current waiting queue, waits for each run to finish or fail before starting the next, reports the active claim and position, refreshes counts after every attempt, and continues past failures. It does not rerun already-decided or referred claims. The same button and six summary cards remain.

Diagnostic work also preserves saved outcomes when the final agent reply fails: a structured 502 response reports a safe error category and saved status/payment, with the traceback logged under the claim id. Backend text errors and request timeouts become tool error messages. The exact original exceptions have not been established from the generic 500 banners; no live-model retry or development claim mutation is part of this correction.

Sequential-processing verification: the deferred-response unit and browser tests prove a second waiting claim does not start until the first completes; failure tests verify the remaining queue continues. Stubbed failure tests preserve approved/paid, approved/unpaid, referred and declined work. `npm run check` passed with 103 Python tests (99.36% coverage), 52 dashboard tests (95.42% statements), and 22 browser tests.

## Automatic stale-run recovery

The student requested automatic reruns after two minutes and human referral after three stalled attempts. New runs record their start time and attempt count in SQLite schema version 2. A backend watchdog checks every five seconds even when the dashboard is closed. It waits for the current worker to exit, then retries an undecided/unpaid claim at least two minutes old, refreshing its timestamp. Attempts 2 and 3 are reruns; if attempt 3 is stale, the system records a human referral with an operational explanation, without another model call. The normal handler approval/denial workflow then applies.

The guarded rerun API is POST /api/claims/{id}/rerun. Saved decisions, payments and existing pre-upgrade claims with no trustworthy start time are excluded. The existing pending records are deliberately left unchanged, as requested. Agent requests time out after 30 seconds without SDK retries, and a 90-second between-model-turn budget bounds prolonged reasoning. A worker is never duplicated merely because its age exceeds two minutes.

Verification uses a simulated clock at 119 and 120 seconds; it checks fresh cooldowns, two retries followed by human review, saved-decision protection, active-worker exclusion, failure accounting, watchdog startup/shutdown and continued monitoring after errors. The claim page shows attempt counts and follows automatic escalation. Tests never wait two real minutes or call a live model. Full checks pass with 118 Python tests (99.10% coverage), 53 dashboard tests (95.42% statements), and 22 browser tests.
