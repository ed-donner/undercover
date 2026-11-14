# Plan: the claims pilot

This plan builds the pilot in `docs/SPEC.md`: a backend that holds the claims queue and enforces the rules, the UnderCover Agent that decides claims through the backend's API, and a dashboard where the handlers watch the queue, read each decision, follow the agent step by step and sign off large payouts.

## The approach

- **The backend is the single source of truth and the rule keeper.** Everything the agent reads or writes goes through the API, so the rules (the $1,000 sign-off limit, one decision per claim, payment only after a valid approval) live in one place in code, not in the prompt. The agent can try to pay a large claim; the backend refuses it.
- **SQLite with the standard library's `sqlite3`.** No ORM: the data is small and the queries are simple. The database is seeded from `data/` by naming each file it loads, so `data/evals/` is never read. Each record's full JSON is stored as it is in `data/`, alongside the columns we query or update (status, decision, payment).
- **The agent's instructions live in the backend** (`backend/instructions.md`), served by `GET /api/instructions`. The agent fetches them at the start of each run and the dashboard shows the same text, so what the team reads is exactly what the agent gets.
- **Steps are reported by the agent's runner.** `run()` streams the agent's progress and posts each step (a tool call, a tool result, a final message) to the backend. The dashboard polls the steps while a claim is in progress. Polling every second is simpler than websockets and good enough for three handlers.
- **The agent sees only what it needs.** The policy comes with its plan limits and add-ons; the customer comes as claim history only, with no contact details or date of birth.
- **The backend starts the agent.** `POST /api/claims/{id}/run` starts `agent.run(claim_id, thread_id)` as a background task, so the dashboard's Run button works without a separate worker. The agent still calls the backend over HTTP for everything. The run's first act is `start_claim`, which moves the claim to in progress, so a run from the command line shows on the dashboard the same way, and the end-to-end tests can play the agent's part without a model.

### Claim states

| State | API value | Color | How a claim gets there |
|---|---|---|---|
| Waiting | `waiting` | Cerulean | Seeded; or the agent's run failed |
| In progress | `in_progress` | Marigold | The agent's runner called `start_claim` |
| Waiting for sign-off | `awaiting_signoff` | Coral | Agent approved a payout over $1,000 |
| Decided | `decided` | Sea Green | Agent declined, referred or approved up to $1,000; or a handler signed off |

### The API

Every operation has an `operation_id`, a one-line docstring and no optional inputs.

| Method and path | `operation_id` | Used by |
|---|---|---|
| `GET /api/health` | `health` | dashboard |
| `GET /api/claims` | `list_claims` | dashboard |
| `GET /api/claims/{claim_id}` | `get_claim` | agent, dashboard |
| `GET /api/policies/{policy_id}` | `get_policy` | agent, dashboard |
| `GET /api/customers/{customer_id}/history` | `get_claim_history` | agent, dashboard |
| `GET /api/policy-wording` | `get_policy_wording` | agent, dashboard |
| `GET /api/instructions` | `get_instructions` | agent, dashboard |
| `GET /api/handlers` | `list_handlers` | dashboard |
| `POST /api/claims/{claim_id}/run` | `run_agent` | dashboard |
| `POST /api/claims/{claim_id}/start` | `start_claim` | agent runner |
| `POST /api/claims/{claim_id}/steps` | `record_step` | agent runner |
| `GET /api/claims/{claim_id}/steps` | `list_steps` | dashboard |
| `POST /api/claims/{claim_id}/decision` | `record_decision` | agent |
| `POST /api/claims/{claim_id}/payment` | `pay_claim` | agent, dashboard |
| `POST /api/claims/{claim_id}/signoff` | `sign_off` | dashboard |

A decision is `{decision: approve | decline | refer, payout, reason, policy_section}`. The payout is 0 unless the decision is approve.

### Out of scope for the pilot

As the spec says: the claims manual, sign-in, real payments and messages to customers. Scoring the agent against `data/evals/` is how UnderCover checks the agent's work, but the spec doesn't ask the pilot to build that tool, so this plan doesn't. Nothing here opens `data/evals/`.

## Phase 1: the database and the read API

Build `backend/db.py` (connection, schema and seed), `backend/seed.py` (`uv run -m backend.seed` rebuilds the database) and the read operations. The database path is `UNDERCOVER_DB`, defaulting to `backend/undercover.db` (already ignored by `*.db`). The backend creates and seeds the database on startup if the file is missing. Add `npm run seed`.

- [x] `npm run seed` creates the database with 25 claims, 50 policies, 49 customers, 3 handlers and the plans and company settings, all claims `waiting`
- [x] The seed names each file it reads; a test checks that no path under `data/evals/` is read and that the claim ids match `data/claims.json` exactly
- [x] `GET /api/claims` returns 25 claims with id, type, summary, amount claimed, submitted date and status
- [x] `GET /api/claims/CLM-1001` returns the story, the items and the documents; an unknown id returns 404
- [x] `GET /api/policies/POL-2001` returns the policy with the Premium plan's limits and the details of any add-ons
- [x] `GET /api/customers/CUS-3001/history` returns the previous claims only, with no email, phone, address or date of birth
- [x] `GET /api/policy-wording`, `GET /api/instructions` and `GET /api/handlers` return the wording, the instructions and the 3 handlers
- [x] Every route has an `operation_id` and a docstring; a test walks the OpenAPI schema to check this and that no input is optional
- [x] `npm run check:python` passes

## Phase 2: decisions, payments, sign-off and steps

Build the write operations and the rules, with each rule enforced in the backend and tested on its own.

- [x] `record_decision` is accepted only for a claim `in_progress`; an approve over $1,000 moves it to `awaiting_signoff`, anything else to `decided`
- [x] A decline or refer with a payout other than 0, or an unknown decision value, is rejected with 422
- [x] `pay_claim` succeeds for an approved claim up to $1,000 when the amount equals the payout, and records the payment
- [x] `pay_claim` returns 409 with a clear message for: an approve over $1,000 without sign-off, an amount that differs from the payout, a decline or refer, a claim with no decision and a claim already paid
- [x] `sign_off` needs a handler with `can_approve_over_limit`; it records who signed and when and moves the claim to `decided`; after that `pay_claim` with the payout succeeds
- [x] `sign_off` is rejected for a claim not `awaiting_signoff` and for an unknown handler or one without the authority
- [x] `record_step` and `list_steps` store and return the steps in order with their time
- [x] `start_claim` moves a `waiting` claim to `in_progress` and returns 409 for any other state
- [x] `run_agent` starts the agent in the background for a `waiting` claim (stubbed in tests) and returns 409 for any other state; if the run raises, the claim goes back to `waiting` with an error step
- [x] `npm run check:python` passes with coverage of at least 80%

## Phase 3: the UnderCover Agent

Rewrite `agent/main.py` around the claims API: tools for `get_claim`, `get_policy`, `get_claim_history`, `get_policy_wording`, `record_decision` and `pay_claim`, each a thin call to the backend. When the backend refuses (a 4xx), the tool returns the backend's message to the model rather than raising, so the agent learns, for example, that a payment waits for sign-off. Write `backend/instructions.md`: the role, the steps for each claim, how to work out a payout from the wording (limits, deductibles, waiting periods), the $1,000 rule, and the shape of the reason (two or three sentences, naming the policy section). `run(claim_id, thread_id)` calls `start_claim` (and stops if the backend refuses), fetches the instructions, streams the agent and posts each step. Add `uv run -m agent CLM-1001` for a manual run.

- [x] Tests with a stub model drive a full run on CLM-1001: the agent reads the claim, policy, history and wording, records an approval and pays; the backend shows the claim `decided` and paid, and the steps are recorded in order
- [x] A stub run that approves over $1,000 and then tries to pay ends with the claim `awaiting_signoff` and unpaid, and the tool result shows the backend's refusal
- [x] The agent's instructions come from `GET /api/instructions`, not from the agent's code (a test changes the served text and sees it in the system prompt)
- [x] The agent has no tool or code path that reads files in `data/`; a test checks the tool list
- [x] `MODEL_NAME` still selects the model, with `openai/gpt-6-luna` at low reasoning effort by default
- [x] With the backend running, `uv run -m agent CLM-1001` on a real model decides the claim with a payout, a two or three sentence reason and a policy section (one manual run, a few cents, or free with `MODEL_NAME=openrouter/free`)
- [x] `npm run check:python` passes

## Phase 4: the dashboard shell, the queue and the instructions

Set up the brand: Instrument Sans, Instrument Serif and JetBrains Mono from Google Fonts, the colors as CSS variables, light and dark mode from the system setting, rounded panels with no outlines. Add a header with two views, Queue and Instructions, using hash links (`#/`, `#/claims/CLM-1001`, `#/instructions`) so no router library is needed. Add a small typed API client in `dashboard/src/api.ts`.

- [x] The queue lists all 25 claims with id, summary, claim type, amount claimed in the form $1,250.00, submitted date and a state chip in the state's color
- [x] A count of claims in each state sits above the queue
- [x] Clicking a claim opens `#/claims/<id>`
- [x] The Instructions view shows the agent's instructions read only
- [x] Vitest covers the queue, the state chips, money formatting and the instructions view, with fetch stubbed
- [x] Checked in the browser with the Playwright MCP server in light and dark mode: brand fonts and colors, no borders on one edge, readable Marigold and Sea Green text
- [x] `npm run check:ts` passes with coverage of at least 80%

## Phase 5: the claim view, live steps and sign-off

The claim view shows the claim in full: the story, the items, the documents, the policy and plan, the customer's claim history and, once decided, the decision, the payout, the reason and the policy section, with that section's text from the wording. A Run agent button appears on a `waiting` claim. While the claim is `in_progress`, the view polls every second and shows each step as it arrives. On a claim `awaiting_signoff`, a handler with the authority is chosen from a list and Sign off and pay calls `sign_off` and then `pay_claim`.

- [x] The claim view shows the story, items, documents, policy, plan and history for CLM-1001
- [x] Run agent calls `run_agent`; the steps appear one by one while the claim is in progress and polling stops when it leaves that state
- [x] A decided claim shows the decision, payout, reason, policy section and payment status
- [x] A claim waiting for sign-off explains that the payout is over $1,000, lists only handlers with the authority, and after Sign off and pay shows it decided and paid
- [x] Errors from the backend show as a short message in plain English
- [x] Vitest covers each state of the claim view, the polling and the sign-off, with fetch stubbed
- [x] Checked in the browser with the Playwright MCP server: run the agent on a claim with a real model, watch the steps arrive, and sign off a claim over $1,000
- [x] `npm run check:ts` passes

## Phase 6: end-to-end tests and handover

Playwright starts its own backend on port 8001 with `UNDERCOVER_DB` pointing to a fresh database, and the dashboard on port 5174 with its proxy pointed at that backend, so the e2e tests never touch the development database and never call a model. They play the agent's part by calling the same API the agent uses. Update `docs/STATUS.md`, which holds the run instructions (`README.md` is the course's own).

- [x] e2e: the queue shows 25 claims and the state counts
- [x] e2e: a claim started and decided through the API (playing the agent) shows on the claim view with its reason and section, and the queue shows the claim decided
- [x] e2e: an approval over $1,000 shows as waiting for sign-off; an attempt to pay through the API is refused; a handler signs off in the dashboard and the claim shows decided and paid
- [x] e2e: the Instructions view shows the instructions
- [x] The health test still passes
- [x] `npm run check` passes in full
- [x] `docs/STATUS.md` says what's built, how to seed, run, and run the agent on one claim
