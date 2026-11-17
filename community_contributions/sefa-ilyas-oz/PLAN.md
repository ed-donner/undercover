# Plan: the claims pilot

The pilot turns the hello-world skeleton into UnderCover's first claims platform: a backend that holds the queue and enforces the payment rules, the UnderCover Agent that decides claims through the backend's API, and a dashboard where the handlers watch the queue, follow the agent step by step and sign off large payouts.

It works from `docs/SPEC.md` and follows `docs/TECH_STACK.md`, `docs/CODE_STANDARDS.md`, `docs/PROCESS.md` and `docs/BRAND.md`.

## Approach

### Where the rules live

The backend owns every rule. The agent decides, but the backend decides what a decision is allowed to do. The rule that matters most, no payout over $1,000 without a handler's sign-off, is enforced in the payment operation itself, so it holds whatever the agent says or tries. The limit comes from `payout_approval_limit` in `data/company.json`, not from a constant in the code.

### Claim states

| State | Meaning | How a claim gets there |
|---|---|---|
| `waiting` | In the queue, not started | Seeded from `data/claims.json` (its `open` status) |
| `in_progress` | The agent is working on it | The agent starts work on it |
| `awaiting_signoff` | Approved with a payout over $1,000, payment held | The agent records an approval over the limit |
| `decided` | Approved, declined or referred | The agent records a decision at or under the limit, or a handler signs off |

A referral is a decision, so a referred claim is `decided`.

### Payments

Paying is a separate operation that takes the amount, as the tech stack asks. The backend refuses a payment, with `409 Conflict` and a plain reason, when:

- the claim has not been approved
- the amount is not the approved payout
- the claim has already been paid
- the payout is over the limit and no handler has signed off

When a handler signs off on a claim, the backend records the sign-off and makes the payment of the approved payout in the same step, then marks the claim `decided`. Payments are records only. No money moves.

### Keeping the answer key out of reach

The backend seeds only the files it names: `company.json`, `plans.json`, `policies.json`, `customers.json`, `handlers.json`, `claims.json` and `policy_wording.md`. It never reads `data/evals/` or `data/security/`, so nothing the agent can reach through the API can show it the handlers' decisions. The agent has no file access at all: every tool is a call to the backend.

The agent gets the customer's claim history, not their contact details, since it needs the one and not the other.

### The agent

`agent/` keeps its single entry point, `run(claim_id, thread_id)`. It:

1. fetches its instructions from the backend (`GET /api/instructions`), so the dashboard and the agent always show the same text
2. marks the claim `in_progress`
3. runs `create_agent` with tools for reading the claim, the policy with its plan, the claim history and the policy wording, recording a decision and paying a claim
4. streams the run and posts each step (a tool call, a tool result or the model's reply) to the backend, so the dashboard can show the work as it happens
5. if the run ends without a decision, refers the claim with the reason "The agent did not reach a decision", so no claim is left stuck in `in_progress`

A decision carries the decision (`approve`, `decline` or `refer`), the payout (0 unless approved), two or three sentences of reasons and the relevant section of the policy wording, such as "Section 3, Trip Delay".

The instructions live in the backend as `backend/instructions.md`. They tell the agent to read everything before deciding, to follow the policy wording, to work out the payout from the plan's limits and the deductible, and, once it approves a claim, to pay it. For a payout over the limit the payment will be refused until a handler signs off. That is expected, and the agent says so in its reply.

The model is `openai/gpt-6-luna` with low reasoning effort, or `MODEL_NAME` when set, as the skeleton does now. Tests always use a stub model.

### Running the agent from the dashboard

The backend runs the agent in the background so the request returns at once: one operation for a single claim and one that works through every `waiting` claim in order. The agent then talks to the backend over HTTP like any other client. There is also a command line: `uv run -m agent CLM-1001`.

### Storage

SQLite through Python's built-in `sqlite3`, with no ORM. Records keep the shape they have in `data/`, stored as JSON in a table per kind, with columns only for what we query or change: a claim's state, its decision, its sign-off and its payment, plus a table of agent steps. The database file is `backend/undercover.db` (already ignored by git), or the path in `UNDERCOVER_DB`, which the tests and the end-to-end run use for a database of their own. `uv run -m backend.seed` rebuilds the database from `data/`, and the backend seeds it on startup when it is empty.

### The dashboard

Three views, with hash routing (`#/`, `#/claims/CLM-1001`, `#/instructions`) and no router library:

- **Queue**: every claim with its id, customer, type, amount claimed and state, a count for each state, and a "Work the queue" button.
- **Claim**: the story, items, documents and policy; the decision with its payout, reasons and policy section; the payment; the agent's steps, refreshed every two seconds while the claim is `in_progress`; a "Run agent" button for a `waiting` claim; and, for a claim `awaiting_signoff`, a choice of handler and a "Sign off and pay" button.
- **Instructions**: the agent's instructions, read only.

It follows `docs/BRAND.md`: Instrument Sans, Instrument Serif and JetBrains Mono from Google Fonts, the light and dark surfaces, rounded panels with no outline, and the states in Sea Green, Marigold, Coral and Cerulean. Money shows as $1,250.00.

### The API

Every operation has an `operation_id`, a one-line docstring and no optional inputs.

| Method and path | `operation_id` | What it does |
|---|---|---|
| `GET /api/health` | `health` | Check that the backend is running |
| `GET /api/claims` | `list_claims` | The queue, with each claim's state |
| `GET /api/claims/{claim_id}` | `get_claim` | One claim in full, with its decision, sign-off and payment |
| `GET /api/policies/{policy_id}` | `get_policy` | A policy with its plan's limits and its add-ons |
| `GET /api/customers/{customer_id}/history` | `get_claim_history` | A customer's earlier claims |
| `GET /api/policy-wording` | `get_policy_wording` | The policy wording |
| `GET /api/instructions` | `get_instructions` | The agent's instructions |
| `GET /api/handlers` | `list_handlers` | The claims handlers |
| `POST /api/claims/{claim_id}/start` | `start_claim` | Mark a waiting claim in progress |
| `POST /api/claims/{claim_id}/decision` | `record_decision` | Record the agent's decision |
| `POST /api/claims/{claim_id}/payment` | `pay_claim` | Pay an approved claim the given amount |
| `POST /api/claims/{claim_id}/signoff` | `sign_off_claim` | A handler signs off and the payout is paid |
| `GET /api/claims/{claim_id}/steps` | `list_steps` | The agent's steps on a claim |
| `POST /api/claims/{claim_id}/steps` | `add_step` | Record one step of the agent's work |
| `POST /api/claims/{claim_id}/run` | `run_agent` | Run the agent on one claim in the background |
| `POST /api/queue/run` | `run_queue` | Run the agent on every waiting claim in the background |

## Phase 1: the records and the read API

Builds the SQLite database, the seeding from `data/` and the read operations. Everything later builds on these.

- `backend/db.py`: the schema, the connection (`UNDERCOVER_DB` or `backend/undercover.db`) and the seeding
- `backend/seed.py`: `uv run -m backend.seed` rebuilds the database
- `backend/main.py`: `list_claims`, `get_claim`, `get_policy`, `get_claim_history`, `get_policy_wording`, `get_instructions`, `list_handlers`, with 404 for an unknown id
- `backend/instructions.md`: the agent's instructions
- Tests against a temporary database

Success criteria:

- [x] `uv run -m backend.seed` creates `backend/undercover.db` with 25 claims, 50 policies, 49 customers and 3 handlers
- [x] `GET /api/claims` returns 25 claims, all `waiting`
- [x] `GET /api/claims/CLM-1001` returns the claim's story, items and documents, with no decision
- [x] `GET /api/policies/POL-2001` returns the policy with the Premium plan's limits
- [x] `GET /api/customers/CUS-3001/history` returns CLM-0412 and no contact details
- [x] `GET /api/policy-wording` returns the text of `data/policy_wording.md`
- [x] `GET /api/claims/CLM-9999` returns 404
- [x] A test shows the seeding reads no file under `data/evals/` or `data/security/`
- [x] A test shows every route has an `operation_id` and a docstring
- [x] `npm run check:python` passes, with coverage at 80% or more

## Phase 2: decisions, payments and sign-off

Adds the operations that change a claim and the rules that guard them, including the $1,000 sign-off rule. This is the phase that makes the pilot safe, so its tests cover each refusal.

- `start_claim`, `record_decision`, `pay_claim`, `sign_off_claim`, `add_step`, `list_steps`
- The state changes and the payment rules from the approach above
- Request bodies with every field required

Success criteria:

- [x] `start_claim` moves a `waiting` claim to `in_progress`
- [x] Recording a decline or a referral, or an approval of $1,000.00 or less, moves the claim to `decided`
- [x] Recording an approval of $1,000.01 or more moves the claim to `awaiting_signoff`
- [x] Paying an approved claim at or under the limit records the payment
- [x] Paying a claim over the limit before sign-off returns 409 and records nothing
- [x] Paying a declined or referred claim, paying the wrong amount and paying twice each return 409
- [x] Signing off a claim `awaiting_signoff` records the handler and the payment, and moves it to `decided`
- [x] Signing off a claim in any other state, or with an unknown handler, is refused
- [x] `record_decision` refuses a decision that isn't `approve`, `decline` or `refer`
- [x] Steps posted to a claim come back from `list_steps` in order
- [x] `npm run check:python` passes, with coverage at 80% or more

## Phase 3: the UnderCover Agent

Replaces the skeleton's hello-world agent with the claims agent, its tools and its step reporting, and lets the backend run it.

- `agent/main.py`: the tools, the instructions fetched from the backend, `run(claim_id, thread_id)` with streaming steps and the fallback referral
- `agent/__main__.py`: `uv run -m agent CLM-1001`
- `run_agent` and `run_queue` in the backend, running the agent in the background
- Tests with a stub model and the backend's `TestClient`

Success criteria:

- [x] A stub-model test runs a claim end to end: the agent reads the claim, policy, history and wording, approves CLM-1001 with a payout of $420.00, pays it, and the claim ends `decided` and paid
- [x] A stub-model test approves a claim over $1,000 and tries to pay it: the payment is refused, nothing is paid and the claim is `awaiting_signoff`
- [x] A stub-model test that never records a decision leaves the claim `decided` as a referral
- [x] After a run, `list_steps` shows the tool calls and the agent's final reply in order
- [x] A test shows the agent's instructions come from `GET /api/instructions`
- [x] A test shows `MODEL_NAME` still chooses the model
- [x] With the backend running and a key in `.env`, `uv run -m agent CLM-1001` records a decision on CLM-1001 with reasons and a policy section (one live run, a few cents, or free with `MODEL_NAME=openrouter/free`)
- [x] `POST /api/claims/CLM-1001/run` returns at once and the claim moves to `in_progress` (tested with a stub agent)
- [x] `npm run check:python` passes, with coverage at 80% or more

## Phase 4: the dashboard's queue and instructions

Builds the dashboard's frame, the brand and the two simpler views.

- `dashboard/src/api.ts`: typed calls to the backend
- Hash routing, the queue view and the instructions view
- The brand: fonts in `index.html`, colors and surfaces as CSS variables, light and dark modes
- Vitest tests with `fetch` stubbed

Success criteria:

- [x] The queue lists 25 claims with id, customer, type, amount and state, and a count for each state
- [x] Clicking a claim goes to `#/claims/<id>`
- [x] "Work the queue" calls `run_queue`
- [x] The instructions view shows the text from `GET /api/instructions`, with no way to edit it
- [x] Money shows as $1,250.00 and the states use the brand colors
- [x] Checked in the browser with the Playwright MCP server, in light and dark mode
- [x] `npm run check:ts` passes, with coverage at 80% or more and no `any`

## Phase 5: the claim view, the live steps and sign-off

Builds the view where a handler reads a claim, follows the agent and signs off.

- The claim view: story, items, documents, policy, decision, payment and steps
- Polling every two seconds while the claim is `in_progress`
- "Run agent" for a `waiting` claim, and handler choice with "Sign off and pay" for a claim `awaiting_signoff`
- Vitest tests with `fetch` stubbed

Success criteria:

- [x] The claim view shows the story, items, documents and policy for CLM-1001
- [x] A decided claim shows the decision, payout, reasons and policy section
- [x] A claim in progress shows new steps as they arrive, without a reload
- [x] "Run agent" shows only on a `waiting` claim and calls `run_agent`
- [x] A claim `awaiting_signoff` shows the held payout and the sign-off control; signing off shows the claim `decided` and paid, with the handler's name
- [x] Checked in the browser with the Playwright MCP server: a live run on one claim shows its steps and its decision
- [x] `npm run check:ts` passes, with coverage at 80% or more and no `any`

## Phase 6: end-to-end tests and the docs

Ties it together with Playwright tests that never call a model, and brings the docs up to date.

- `playwright.config.ts`: the end-to-end run uses its own freshly seeded database through `UNDERCOVER_DB`, its own backend on port 8100 and its own dashboard on port 5174, so it never touches the database you use with `npm run dev`. The dashboard's proxy target comes from `BACKEND_URL`, defaulting to port 8000
- `e2e/`: the agent's work is played through the API (start, steps, decision), so the tests are fast, free and the same every time
- `docs/STATUS.md` with how to run the pilot. The root `README.md` is the course's own, so the pilot's notes stay in `docs/STATUS.md`

Success criteria:

- [x] An end-to-end test: the queue shows 25 claims
- [x] An end-to-end test: a claim with steps and a decision shows both in its view
- [x] An end-to-end test: a claim approved over $1,000 shows as waiting for sign-off, a payment through the API is refused, and signing off in the dashboard shows it decided and paid
- [x] An end-to-end test: the instructions view shows the instructions
- [x] `npm run check` passes in full
- [x] `docs/STATUS.md` says what is built and how to run it

## Not in the pilot

As `docs/SPEC.md` says: no claims manual, no sign-in, no real payments and no messages to customers. Measuring the agent against `data/evals/` is for later, and nothing in this build opens that folder.
