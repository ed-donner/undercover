# Plan: the claims pilot

This plan builds the pilot in `docs/SPEC.md`: a backend that holds UnderCover's claims, the UnderCover Agent that decides them, and a dashboard where the handlers watch the queue, read each decision, follow the agent as it works, and sign off large payouts.

It builds on the hello-world skeleton described in `docs/STATUS.md`. Each phase builds on the last, ends with every check green, and is committed.

## Key decisions

These are the choices that shape the build. They are worth reviewing before implementation starts.

1. **The backend is the only source of truth, and the agent is just another client of its API.** The agent reaches claims, policies, claim history, the policy wording and its own instructions only through HTTP calls, as `docs/TECH_STACK.md` requires. This means the rules that matter (the $1,000 sign-off, valid decisions) are enforced in one place, the backend, and hold no matter what the model does.
2. **SQLite through Python's built-in `sqlite3` module**, with no ORM. The pilot has a handful of tables, and plain SQL keeps it simple. The database file (`backend/undercover.db`, already ignored by git) is created and seeded from `data/` the first time the backend starts. Deleting the file starts afresh. The path can be changed with the `UNDERCOVER_DB` environment variable, which the tests use to get a clean database each time.
3. **Records go in SQLite; fixed reference documents stay as files.** Claims, policies, customers, handlers, decisions, payments, sign-offs and the agent's steps live in the database. The plans, the company settings and the policy wording are read from `data/` at startup, because nothing in the pilot changes them.
4. **`data/evals/` and `data/security/` are never loaded.** The seed reads a fixed list of files, so the answer key cannot reach the API, and therefore cannot reach the agent. A test guards this.
5. **Personal data is kept to what the agent needs.** The agent can read a customer's earlier claims, but there is no API route that returns their phone, email, date of birth or address. The dashboard shows the customer's name only.
6. **Paying is a separate operation, and the backend blocks it.** The agent records its decision first, then calls `pay_claim` with the amount. The backend refuses the payment unless the claim is approved, the amount matches the approved payout, it hasn't been paid already, and (when the payout is over $1,000) a handler has signed off. When a handler signs off, the backend releases the payment of the approved payout. No real money moves: a payment is a row in the database.
7. **The agent's instructions live in the backend**, in `backend/instructions.md`, and are served by `GET /api/instructions`. The agent fetches them at the start of every run, and the dashboard shows the same text read only. The agent fetches the full policy wording (`data/policy_wording.md`) with a tool, and works from the wording alone, not the claims manual, as the spec asks.
8. **The agent's steps are recorded as it works.** The entry point streams the agent's progress and posts each step (each tool call, its result and the final reply) to the backend. The dashboard polls the claim every two seconds while it is in progress, so the handlers see the steps appear. Polling is simpler than websockets and fast enough for a person watching.
9. **The dashboard can start the agent on a claim.** A "Run the agent" button calls `POST /api/claims/{claim_id}/run`, which runs the agent's entry point in the background. There is also a command line, `uv run -m agent CLM-1001`, and `uv run -m agent --queue` to work every waiting claim in turn. Without some trigger the handlers could not watch the agent work, so this is the smallest addition that makes the spec's "what the agent is doing, step by step" usable.
10. **Hash routing in the dashboard** (`#/`, `#/claims/CLM-1001`, `#/instructions`), with no router library. Three pages don't need one, and every page still has a link that can be shared.

## Claim states

| State | Label on screen | How a claim gets there |
|---|---|---|
| `waiting` | Waiting | Seeded from `data/claims.json`, or returned to the queue when a run ends without a decision |
| `in_progress` | In progress | The agent starts work on it |
| `awaiting_sign_off` | Waiting for sign-off | The agent approves with a payout over $1,000 |
| `decided` | Decided | The agent declines, refers, or approves with a payout of $1,000 or less; or a handler signs off |

Colors follow `docs/BRAND.md`: Decided in Sea Green, Waiting for sign-off in Marigold, In progress in Coral, Waiting in Cerulean, and Raspberry for alerts such as a blocked payment.

## The API

Every operation has an `operation_id` and a one-line docstring, and takes no optional inputs.

| Method and path | `operation_id` | What it does |
|---|---|---|
| `GET /api/health` | `health` | Check that the backend is running (exists) |
| `GET /api/claims` | `list_claims` | The queue: id, customer name, type, summary, amount claimed, submitted date, status, decision and payout |
| `GET /api/claims/{claim_id}` | `get_claim` | The claim in full, with its decision, payment and sign-off when they exist |
| `GET /api/claims/{claim_id}/steps` | `list_steps` | The agent's steps on the claim, oldest first |
| `GET /api/policies/{policy_id}` | `get_policy` | The policy, with its plan's limits and its add-ons spelled out |
| `GET /api/customers/{customer_id}/claims` | `get_claim_history` | The customer's earlier claims, and nothing else about them |
| `GET /api/policy-wording` | `get_policy_wording` | The policy wording's version and text |
| `GET /api/instructions` | `get_instructions` | The agent's instructions |
| `GET /api/handlers` | `list_handlers` | The claims handlers |
| `POST /api/claims/{claim_id}/start` | `start_claim` | Move a waiting claim to in progress |
| `POST /api/claims/{claim_id}/steps` | `record_step` | Add a step: its kind (`tool_call`, `tool_result`, `reply` or `error`) and text |
| `POST /api/claims/{claim_id}/decision` | `record_decision` | Record approve, decline or refer, with the payout, the reasons and the policy section |
| `POST /api/claims/{claim_id}/payments` | `pay_claim` | Pay the claim the given amount, if the rules allow it |
| `POST /api/claims/{claim_id}/sign-off` | `sign_off` | A handler signs off a large payout, which releases its payment |
| `POST /api/claims/{claim_id}/return` | `return_to_queue` | Put an in-progress claim back to waiting |
| `POST /api/claims/{claim_id}/run` | `run_agent` | Start the agent on a waiting claim in the background |

Errors use plain status codes with a short message: 404 for an unknown id, 409 for an action that doesn't fit the claim's state, 403 for a payment that needs sign-off, 422 for an invalid body.

## Phase 1: The backend's records and read API

**What it builds.** The SQLite database, the seed from `data/`, and the read operations: `list_claims`, `get_claim`, `get_policy`, `get_claim_history`, `get_policy_wording`, `get_instructions` and `list_handlers`. A first version of `backend/instructions.md`.

**Why first.** Everything else, the agent and the dashboard alike, reads these records. Getting the data model and the seed right first means the later phases only add behavior.

**Shape.** `backend/db.py` opens the database, creates the tables and seeds them when the file is new. `backend/main.py` holds the routes, with Pydantic models for the responses. Tests use a temporary database through `UNDERCOVER_DB`.

Success criteria:

- [x] `uv run pytest -q backend` passes, with tests for every read operation, including a 404 for an unknown claim, policy and customer.
- [x] A fresh backend seeds 25 claims, all `waiting`: `curl -s localhost:8000/api/claims` returns 25 items, and none has a status other than `waiting`.
- [x] `curl -s localhost:8000/api/claims/CLM-1001` returns the story, the three items, the four documents and `"status": "waiting"`, with no decision.
- [x] `curl -s localhost:8000/api/policies/POL-2001` returns the Premium plan's limits (trip delay maximum 800.0, deductible 50.0).
- [x] `curl -s localhost:8000/api/customers/CUS-3001/claims` returns CLM-0412, and the response contains no email, phone, date of birth or address.
- [x] `curl -s localhost:8000/api/policy-wording` returns version `2026.1` and text that contains "How we work out your payment".
- [x] A test asserts that no API response contains any claim id or text from `data/security/`, and that the seed's file list contains nothing under `data/evals/` or `data/security/`.
- [x] `grep -rn "evals" backend agent --include=*.py` finds nothing outside tests.
- [x] Restarting the backend keeps the database as it was; deleting `backend/undercover.db` and restarting reseeds it.
- [x] `npm run check:python` passes, with coverage at or above 80%.

## Phase 2: Decisions, payments and the sign-off rule

**What it builds.** The write operations: `start_claim`, `record_step`, `list_steps`, `record_decision`, `pay_claim`, `sign_off` and `return_to_queue`, with the state changes in the table above.

**Why now, before the agent.** These are the rules the business cares most about: a payout over $1,000 must never be paid without a handler's sign-off, "even if the agent tries to pay". Building and testing them in the backend first, with no model involved, proves the guard holds on its own. The agent then only has to call the API.

**The rules the backend enforces.**

- A decision is `approve`, `decline` or `refer`. The payout is zero or more, and must be zero unless the decision is `approve`. The reasons and the policy section must not be empty. A claim can be decided only while it is in progress.
- An approval with a payout over the `payout_approval_limit` in `data/company.json` ($1,000.00) moves the claim to `awaiting_sign_off`. Every other decision moves it to `decided`.
- `pay_claim` is refused with 409 when the claim isn't approved, the amount differs from the approved payout, or it has already been paid; and with 403 when the payout is over the limit and no handler has signed off.
- `sign_off` needs a claim in `awaiting_sign_off` and a handler who exists and `can_approve_over_limit`. It records the sign-off, records the payment of the approved payout and moves the claim to `decided`.

Success criteria:

- [x] `uv run pytest -q backend` passes, with a test for each rule above and each refusal.
- [x] Through the API: start CLM-1001, record an approval of $420.00, pay $420.00. The claim is `decided` with a payment of $420.00. Paying again returns 409.
- [x] Through the API: start CLM-1003, record an approval of $3,750.00. The claim is `awaiting_sign_off`. `pay_claim` with 3750.00 returns 403 and no payment is recorded.
- [x] `sign_off` on CLM-1003 with `HND-01` returns 200; the claim is `decided`, with the sign-off and a payment of $3,750.00. A second `sign_off` returns 409.
- [x] A payout of exactly $1,000.00 goes straight to `decided` and can be paid without sign-off.
- [x] Recording a decline with a payout of 50 returns 422; deciding a `waiting` claim returns 409; `sign_off` with an unknown handler returns 404.
- [x] Steps posted to a claim come back from `list_steps` in the order they were posted.
- [x] `return_to_queue` moves an in-progress claim back to `waiting`.
- [x] `npm run check:python` passes, with coverage at or above 80%.

## Phase 3: The UnderCover Agent

**What it builds.** The agent in `agent/`, built with LangChain's `create_agent` on OpenRouter, keeping the skeleton's model choice (`openai/gpt-6-luna` with low reasoning effort, or `MODEL_NAME`).

- **Tools**, each a thin wrapper over one API operation: `get_claim`, `get_policy`, `get_claim_history`, `get_policy_wording`, `record_decision` and `pay_claim`. When the backend refuses something, the tool returns the refusal message to the model instead of raising, so the agent can see that, for example, a payment is waiting for sign-off.
- **Instructions** in `backend/instructions.md`: read the claim, the policy, the claim history and the policy wording; decide from the wording alone; refer when the claim needs someone's judgment or a document is missing; work out the payout as section 10 of the wording describes; record the decision with two or three sentences of reasons and the relevant section; then, for an approval, pay the payout, knowing that a payout over $1,000 waits for a handler's sign-off.
- **The entry point** `run(claim_id, thread_id)`: fetches the instructions, calls `start_claim`, streams the agent and posts each step to `record_step`, and returns the final reply. If the run ends without a decision, or the model fails, it records an `error` step and calls `return_to_queue`, so no claim is left stuck in progress.
- **The command line**: `uv run -m agent CLM-1001` runs one claim; `uv run -m agent --queue` runs every waiting claim in turn.
- **`run_agent` in the backend**: checks the claim is waiting, then calls the entry point in a FastAPI background task with a new thread id, and returns 202 at once.

**Why this way.** Giving the agent one tool per API call keeps its steps easy to read on the dashboard, and keeps every rule in the backend. Recording steps from the entry point, not from the tools, means the agent's own reply is recorded too, and the agent can't forget to log.

Success criteria:

- [x] `uv run pytest -q agent` passes. Tests use the skeleton's stub model with scripted tool calls against the real backend through `TestClient`; no test calls a model.
- [x] A stubbed run on CLM-1001 that reads, approves $420.00 and pays leaves the claim `decided` and paid, with each tool call, tool result and the reply in `list_steps`.
- [x] A stubbed run on CLM-1003 that approves $3,750.00 and then tries to pay leaves the claim `awaiting_sign_off` with no payment, and the steps show the payment was refused.
- [x] A stubbed run that ends without a decision, and one where the model raises, each leave the claim `waiting` with an `error` step.
- [x] A backend test with the entry point stubbed shows `run_agent` returns 202 for a waiting claim and 409 for one that isn't.
- [x] Live, once (a few cents on the default model, or free with `MODEL_NAME=openrouter/free`): `uv run -m agent CLM-1001` ends with the claim decided, a payout, two or three sentences of reasons and a policy section.
- [x] Live, once: `uv run -m agent CLM-1003`. Whatever the agent decides, the result obeys the rule: if it approves over $1,000, the claim is `awaiting_sign_off` and has no payment.
- [x] `npm run check:python` passes, with coverage at or above 80%.

## Phase 4: The dashboard's queue and claim pages

**What it builds.** The brand and the two main pages.

- **Brand**: Instrument Sans, Instrument Serif and JetBrains Mono from Google Fonts; the colors as CSS variables; light and dark mode following the system setting; rounded panels with no outline; money formatted as $1,250.00; ids and amounts in JetBrains Mono.
- **The queue** (`#/`): a count of claims in each state, then a table of every claim with its id, customer, type, summary, amount claimed, status badge and, once decided, the decision and payout. Each row links to the claim.
- **The claim** (`#/claims/CLM-1001`): the story, the items with their amounts, the documents, and the policy's plan and trip; then the agent's decision, payout, reasons and policy section, and whether it has been paid.
- A small typed API client, `dashboard/src/api.ts`, with types that match the backend's responses.

**Why split from the next phase.** These pages only read data, so they can be built and tested against the backend from Phases 1 and 2. The live and interactive parts come next.

Success criteria:

- [x] `npm run check:ts` passes: Prettier, ESLint, `tsc` in strict mode with no `any`, and vitest with coverage at or above 80%. Component tests stub `fetch`.
- [x] With `npm run dev` running, in the browser through the Playwright MCP server: the queue shows 25 claims, all Waiting, with the four state counts.
- [x] Clicking CLM-1001 opens `#/claims/CLM-1001` with the story, the three items, the four documents and the plan.
- [x] After the Phase 2 API steps, CLM-1003 shows as Waiting for sign-off in the queue, and its page shows the approval, $3,750.00, the reasons and the section.
- [x] Screenshots in light and dark mode match `docs/BRAND.md`: the right fonts and colors, no one-edge borders, no lines across the top of the page.
- [x] The pages work at a phone width of 390 pixels without scrolling sideways.

## Phase 5: The agent at work, sign-off and the instructions page

**What it builds.** The interactive parts of the dashboard.

- **Run the agent**: a button on a waiting claim that calls `run_agent`.
- **The agent's activity**: a list of steps on the claim page, each with its time and a short, readable line (such as "Read policy POL-2001" or "Payment refused: needs a handler's sign-off"). While the claim is in progress, the page polls every two seconds, and stops when the claim leaves that state.
- **Sign-off**: on a claim waiting for sign-off, an alert saying the payment is held, a choice of handler and a "Sign off and pay" button that calls `sign_off`.
- **The instructions** (`#/instructions`): the agent's instructions, read only, linked from the page header.

Success criteria:

- [x] `npm run check:ts` passes, with vitest tests for the run button, the polling (with fake timers), the sign-off and the instructions page.
- [x] In the browser: on a fresh database, clicking "Run the agent" on CLM-1001 moves it to In progress, the steps appear one by one without a reload, and the page settles on Decided with the decision and reasons. (One live model run.)
- [x] In the browser: on CLM-1003 after the Phase 2 API steps (approved for $3,750.00, waiting for sign-off), choosing Dana Whitfield and clicking "Sign off and pay" moves it to Decided and shows "Paid $3,750.00" and who signed off.
- [x] The run button and sign-off controls appear only in the states where they apply.
- [x] `#/instructions` shows the same text as `GET /api/instructions`, with nothing to edit it.

## Phase 6: End-to-end tests and handover

**What it builds.** Playwright tests for the whole flow, and the documents.

- Playwright starts its own backend on port 8001 with a fresh database file, and its own dashboard on port 5174 that points at it, so the tests never touch the development database. This means a small change to `playwright.config.ts` and to the dashboard's proxy in `vite.config.ts`, which reads the backend's address from an environment variable and defaults to port 8000.
- The tests drive the backend through Playwright's `request` fixture in place of the agent, so no model is called.
- `docs/STATUS.md` describes what's built and how to run it, and a short `README` section says how to start the pilot.

Success criteria:

- [x] `npm run e2e` passes, with tests that: the queue shows 25 waiting claims; a claim page shows its story and documents; the instructions page shows the instructions; steps posted to a claim appear on its page; an approval over $1,000 shows as Waiting for sign-off, a direct payment is refused with 403, and signing off in the dashboard leaves it Decided and paid.
- [x] Running `npm run e2e` twice in a row passes both times, and leaves `backend/undercover.db` unchanged.
- [x] The old health test is replaced or kept passing.
- [x] `docs/STATUS.md` is up to date, and the README tells a new reader how to start the backend, the dashboard and the agent.
- [x] `npm run check` passes in full.

## Not in this plan

These are out of scope for the pilot, per `docs/SPEC.md`, or belong to a later build:

- The claims manual, sign-in, real payments and messages to customers.
- Scoring the agent against `data/evals/`. The spec keeps the answer key for checking the agent later, and `docs/PROCESS.md` says not to open it unless asked.
- Handlers overriding or editing the agent's decisions, and editing its instructions.
