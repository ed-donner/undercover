# Pilot implementation plan

## Objective and scope

Deliver the pilot described in `docs/SPEC.md`: a claims queue, the UnderCover Agent capable of approving, declining or referring each case, and a dashboard for monitoring work and authorizing payouts over $1,000.

The starting point is the existing skeleton: a FastAPI health check, an agent with a health tool and a React page. The initial queue will contain only the 25 claims in `data/claims.json`, from CLM-1001 to CLM-1025. Related records will come from the explicitly required files in `data/`.

The agent will use the complete wording in `data/policy_wording.md`. The claims manual, `data/knowledge.json`, `data/security/`, held-out cases and answer keys in `data/evals/` are outside this implementation. There will be no authentication, real payments, customer messages, AWS resources, distributed execution or features from future briefs. Tests will use synthetic data and a stub model, without paid calls or answer keys.

## Architecture decisions

- Keep FastAPI, SQLite, React/Vite/TypeScript and LangChain `create_agent` with OpenRouter. Use the standard library's `sqlite3`, without adding an ORM for this pilot.
- Persist claims, decisions, authorizations, simulated payments and events in SQLite. Import seed data once per new database, without overwriting existing work on restart. Use independent temporary databases in tests.
- Store payment amounts as integer cents and validate API money inputs with `Decimal`. Do not calculate money with floating point arithmetic. The API will accept and return dollar amounts with cent precision.
- Separate the agent's decision, queue state and payment. `approve`, `decline` and `refer` are decisions; `waiting`, `in_progress`, `waiting_for_sign_off` and `decided` are workflow states. Payments have their own records.
- Convert the initial `open` status to `waiting`. Preserve the order of records in `claims.json` as queue order, using an explicit index.
- Reserve a claim atomically before processing it. A second execution cannot take over an in-progress or completed case.
- The agent will obtain instructions and business data exclusively through the HTTP API. It will not import backend storage modules or open business files. Instructions will have a single source in the backend and a read-only view in the dashboard.
- Persist start, tool call, tool result, decision, authorization, payment and failure events. Display these observable actions without requesting or storing private model reasoning.
- Refresh the queue and events through simple dashboard polling. Start agent executions from the command line in this pilot.
- Use US English, USD amounts and the identity defined in `docs/BRAND.md` throughout the interface. Maintain the plan and its contribution copy in English.

## Phase 1 — Data and persistence

Create the SQLite database and explicit seed loader. This phase establishes the data and states that subsequent phases will use.

Implement a backend storage module, domain models and initialization through FastAPI's application lifecycle. Load claims, customers, policies, plans, handlers, the approval limit from `company.json` and the policy wording. Do not expose internal manual rules present in company settings as agent decision rules. Preserve document text and claim items without losing source information.

Success criteria:

- [x] An empty database receives exactly 25 claims in `waiting`, ordered CLM-1001 through CLM-1025, with the relationships needed to retrieve the customer, history, policy and plan.
- [x] Tests verify preservation of the story, items and documents, including special characters and fractional dollar amounts.
- [x] Initializing twice or restarting the backend does not duplicate records or erase existing decisions, payments or events.
- [x] Tests use temporary databases without changing the development database or original JSON files.
- [x] A test observes the paths read by the seed loader and proves that only allowed files are opened, with no access to `evals/`, `security/`, the manual or additional knowledge.
- [x] `uv run pytest -q backend/tests` passes for this phase's scenarios; `docs/STATUS.md` documents the database location and initialization.

## Phase 2 — API, decisions, authorization and payment rules

Implement small operations with typed contracts. Enforce payment controls in the backend so they also apply when an agent tool is called incorrectly.

Proposed contract, with every input field required:

| Operation | Purpose and main response |
|---|---|
| `GET /api/health` | Preserve `200 {"status":"ok"}`. |
| `GET /api/claims` | List the queue in order, with identifiers, customer, type, amount, state and decision summary. |
| `GET /api/claims/{claim_id}` | Retrieve the full claim, decision, authorization and payment. |
| `GET /api/claims/{claim_id}/context` | Retrieve the customer and history, policy, plan and applicable add-ons. |
| `GET /api/policy-wording` | Retrieve the complete wording and its version. |
| `GET /api/agent/instructions` | Retrieve the instructions the agent actually uses. |
| `GET /api/handlers` | List handlers available for sign-off. |
| `GET /api/claims/{claim_id}/events` | Retrieve ordered events with timestamps, types and content. |
| `POST /api/claims/{claim_id}/start` | Accept `thread_id`, reserve the case and record the start. |
| `POST /api/claims/{claim_id}/events` | Accept `thread_id`, type and content for an execution event. |
| `POST /api/claims/{claim_id}/decision` | Accept `thread_id`, outcome, amount, calculation, explanation and policy section. |
| `POST /api/claims/{claim_id}/sign-off` | Accept `handler_id` and authorize the pending decision. |
| `POST /api/claims/{claim_id}/pay` | Accept the amount and record a simulated payment separately from the decision. |
| `POST /api/claims/{claim_id}/failure` | Accept `thread_id` and a failure description, record the error and return an unfinished execution to the queue. |

Use `404` for missing records, `422` for invalid inputs and `409` for state conflicts. Give every operation a unique `operation_id` and a one-line docstring. Reads will have fixed response shapes, without filters or optional parameters in this pilot.

An approval above the limit moves to `waiting_for_sign_off`, without payment. A permitted handler authorizes that decision, while payment remains a separate operation. The dashboard will call these two operations in sequence, keeping a payment failure visible and allowing a retry without another sign-off. Approvals up to the limit remain in progress until payment; declines and referrals finish in `decided`, preserving their distinct outcomes. A referral completes automated analysis and explicitly leaves the case needing handler review.

Success criteria:

- [x] TestClient verifies `200` responses from read endpoints, the 25 cases in the correct order and `404` for an unknown identifier.
- [x] Reservation accepts only `waiting`; two concurrent attempts produce one reservation and one conflict. Execution writes require the active `thread_id`.
- [x] Tests verify approval, decline and referral transitions, including outcome, calculation, a two- or three-sentence explanation and a policy section reference.
- [x] A $1,000 approval permits payment without sign-off; $1,000.01 stays in `waiting_for_sign_off`, and a direct `/pay` call returns `409` without recording a payment.
- [x] After a permitted handler signs off, payment of the approved amount succeeds and the case becomes `decided`. Missing handlers and handlers without permission cannot authorize payment.
- [x] Reject negative payments, fractions of a cent, amounts different from the approval, payment before a decision and payment for declined or referred cases. Repeating a payment request does not create a second payment.
- [x] Reject changes to a completed or authorized decision so its authorization cannot be reused for another amount.
- [x] Events, authorization and payment survive a backend restart. An execution failure preserves events and never erases an existing decision or completed payment.
- [x] OpenAPI confirms unique `operation_id` values, required inputs and no optional parameters in any operation.
- [x] Backend tests pass, and `docs/STATUS.md` describes the states, operations and payment control.

## Phase 3 — Claims analysis agent

Replace the demonstration agent with an agent that reads the case, retrieves context and wording, decides and records its result through HTTP tools. Preserve `run(claim_id, thread_id)` and stub model injection for tests.

Instructions will explain the analysis order: coverage and dates, documents, exclusions, limits and add-ons, third-party reimbursements, deductible and benefit cap. The result will include `approve`, `decline` or `refer`, a USD amount, the calculation, a two- or three-sentence explanation and the relevant policy section. Missing information or situations the wording does not resolve should lead to referral, without inventing manual rules.

Default to `openai/gpt-6-luna` with low reasoning effort and respect `MODEL_NAME`, including `openrouter/free`. Fetch instructions from the API before creating the agent. Provide only the tools needed for analysis and simulated payment, without a handler sign-off tool. Record calls, results and errors during execution. An over-limit approval ends with the decision awaiting authorization; the agent must not try to bypass the control.

Success criteria:

- [x] A stub model exercises claim, context and wording reads, decision recording and payment, leaving ordered events in the backend.
- [x] Synthetic cases cover approval, decline, referral for a missing document and over-limit approval, without using answer keys.
- [x] Instructions include the section 10 calculation order, item and benefit limits, add-ons and wording references; they do not include rules exclusive to the manual.
- [x] A test proves that the exact instructions returned by the API are passed to `create_agent`.
- [x] Tests confirm the default model, low reasoning effort and use of `MODEL_NAME` when set. All tests run without an OpenRouter key or traffic to a model provider.
- [x] The agent has no sign-off tool. An attempt to pay above the limit without authorization is rejected by the backend and creates no payment.
- [x] HTTP and model failures appear in the activity feed, end execution with an identifiable error and do not leave an undecided claim stuck in progress.
- [x] Agent tests pass, and `docs/STATUS.md` describes configuration and the analysis workflow.

## Phase 4 — Individual runs and queue processing

Add `agent/__main__.py` to run one case or the entire queue sequentially. Fetch cases through the API, select only waiting claims and preserve queue order. Generate a `thread_id` per attempt and use the same `run` function in both modes. This approach meets the pilot's needs without introducing a dispatcher or parallel execution.

Success criteria:

- [x] `uv run -m agent CLM-1001` starts only that case and prints its identifier, outcome, amount and final state; CLI tests use a stub model.
- [x] `uv run -m agent` processes each `waiting` case in API queue order, skipping in-progress cases, cases awaiting sign-off and completed cases.
- [x] Tests show that each attempt uses a distinct `thread_id`, and rerunning the queue does not repeat completed decisions or payments.
- [x] An unknown identifier or unavailable backend produces a useful message and a nonzero exit code.
- [x] A failure is recorded for its case while the remaining queue continues. The summary identifies successes and failures, and the process exits nonzero if any case failed.
- [x] Two executions cannot work on the same case simultaneously, respecting the reservation implemented in phase 2.
- [x] `docs/STATUS.md` includes `uv run -m agent` and `uv run -m agent CLM-1001`, the running-backend prerequisite and required environment variables.

## Phase 5 — Handler dashboard

Build the queue, claim details and a read-only instructions page. Show the four queue states with clear labels. Claim details will show the complete story, items, documents, customer and history, policy and plan, decision, calculation, explanation, policy section and payment status.

Show agent activity in a timeline refreshed by polling, including while a case is in progress. Allow a handler to be selected for pending payment authorization. Display loading, an empty queue, network failures and operation errors, with a way to retry the relevant read or operation.

Apply Instrument Sans and JetBrains Mono, rounded surfaces and the colors in `docs/BRAND.md`, with readable contrast. Use semantic HTML, visible keyboard focus and layouts that work on smaller screens. Do not add controls to edit instructions or start agent executions from the browser.

Success criteria:

- [x] Vitest/Testing Library verifies the queue, all four states, case selection, complete data and approval, decline and referral decisions.
- [x] Tests with controlled timers verify polling updates to the queue and events, and cancellation when leaving the page.
- [x] The instructions page shows the actual text returned by the backend, without editable fields.
- [x] The sign-off flow shows the handler and amount, waits for the backend response and displays completed payment only after `/pay` succeeds.
- [x] A payment failure after authorization remains visible and allows retrying only the payment, without duplication.
- [x] Tests cover loading, an empty queue, API unavailability and authorization errors. Buttons are disabled while their operation is running.
- [x] Through Playwright MCP, inspect the queue, details, instructions and live events in a real browser at 1440 px and 390 px, without horizontal overflow or console errors.
- [x] Through Playwright MCP, inspect keyboard navigation, control labels, focus and amounts such as `$1,250.00`; compare colors and fonts with `docs/BRAND.md`.
- [x] `npm run check:ts` passes with strict TypeScript, no `any` and at least 80% coverage; update `docs/STATUS.md` with the available screens.

## Phase 6 — Integration, verification and delivery

Consolidate complete workflows using the real backend, temporary SQLite storage and a stub model. Integration tests must control the database and agent execution without depending on an OpenRouter key or the development database.

Success criteria:

- [x] Playwright verifies a case moving from `waiting`, displaying events in `in_progress`, and finishing approved and paid, with the decision and explanation in its detail view.
- [x] Playwright verifies an approval above $1,000: the API blocks direct payment before sign-off, the dashboard shows the pending state, a handler authorizes it and exactly one payment is recorded.
- [x] Playwright verifies decline and referral decisions, displaying reasons and policy references without payment or authorization actions.
- [x] An integration check demonstrates persistence of decisions, events and payment after restarting the backend with the same temporary database.
- [x] `uv sync` and `npm install` complete from the repository root; the pre-commit hook is installed. Use Python 3.12 and Node 26 as documented.
- [x] `npm run dev` starts the backend and dashboard; `GET /api/health` returns `200 {"status":"ok"}`, and the browser opens the queue.
- [x] `npm run check` passes in full: Ruff, Pyright, pytest with at least 80% coverage, Prettier, ESLint, TypeScript, Vitest with at least 80% coverage and Playwright.
- [x] Added scripts work on Windows and Linux/macOS, using `uv run` commands or `.mjs` files, without Bash-only syntax.
- [x] `docs/STATUS.md` records installation, startup, database location, both CLI modes, model configuration, authorization, tests and known pilot limitations.
- [x] Review the final diff to confirm there is no access to answer keys, the manual or later-stage data, no committed secrets and no AWS resources.

## Implementation process after review

Implementation was authorized and completed in all six phases. The criteria above were verified through automated tests and browser inspection; see `docs/STATUS.md` for run instructions and results.

Implement the six phases in order. In each phase, build with tests, verify the criteria, mark only proven items, update `docs/STATUS.md` and commit with the hook enabled. Fix failures without disabling rules or reducing coverage. Do not push as part of the implementation itself. After completion, run `npm run check` and report the results and remaining limitations. Publishing the completed build and contribution is separately authorized by the student's subsequent request.
