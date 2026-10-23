# Plan: the claims pilot

This plan builds the pilot in `docs/SPEC.md`. It has three parts: a backend that holds the claims queue and enforces the rules, the UnderCover Agent that decides claims through the backend's API, and a dashboard where the handlers watch the queue, read decisions and sign off large payouts.

It follows `docs/TECH_STACK.md`, `docs/CODE_STANDARDS.md`, `docs/PROCESS.md` and `docs/BRAND.md`. Each phase builds on the one before and ends with a commit.

## The approach

### How the parts fit together

```
dashboard (React)  ──HTTP──▶  backend (FastAPI + SQLite)  ◀──HTTP──  agent (create_agent)
                                     │                                     ▲
                                     └──── "Work the queue" runs ──────────┘
                                           the agent in a background thread
```

- **The backend is the source of truth and the rule keeper.** It holds the claims, their status, the agent's decisions and the payments. The $1,000 sign-off rule lives in the backend's pay operation, not in the agent's instructions. Whatever the agent does, the backend refuses an unsigned payment over the limit. This is what the spec means by "the system must block the payment".
- **The agent talks to the backend only through the API**, as the tech stack asks. It reads the claim, the policy, the claim history and the policy wording through tools, and even fetches its own instructions from the API. That keeps the agent's view of the world explicit: it can see only what an API operation hands it, and no operation reads `data/evals/`.
- **The agent records its decision with a tool call, not as free text.** A `record_decision` tool takes the decision, the payout, the reason and the policy section, and the backend validates them. This gives us a structured decision we can show and check, without parsing the model's prose.
- **"Work the queue" runs the agent inside the backend process**, in one background thread that works the waiting claims one at a time. This is the simplest thing that works for a pilot: no job queue and no extra process to start. `npm run dev` stays the only command.
- **The agent reports its steps to the backend** as it goes, and the dashboard polls for them every two seconds. Polling is simpler than server-sent events or WebSockets and is fast enough for a person watching a claim.

### Claim statuses

| Status in the API | Shown as | When |
|---|---|---|
| `waiting` | Waiting | Seeded from `data/claims.json` (its `open` status) |
| `in_progress` | In progress | The agent has started the claim |
| `awaiting_signoff` | Waiting for sign-off | The agent approved a payout over $1,000 |
| `decided` | Decided | Declined, referred, approved within the limit, or signed off |

A referral is a decision, so a referred claim is Decided with the decision Referred.

### The rules, and where each is enforced

| Rule | Where |
|---|---|
| A payout over $1,000 needs a handler's sign-off | `pay_claim` refuses it with 409 until a handler signs off; signing off releases the payment |
| Pay only what was approved | `pay_claim` refuses any amount other than the approved payout, and any claim that isn't approved or is already paid |
| Decisions follow the policy wording | The agent's instructions, and the wording is one of its tools |
| The agent never sees `data/evals/` | The backend never reads that folder, and the agent reads only through the API; a test checks it |
| Amounts in US dollars | Stored as numbers rounded to cents, shown as $1,250.00 |

The limit comes from `payout_approval_limit` in `data/company.json`, not from a constant in the code.

### The API

Every operation has an `operation_id`, a one-line docstring and only required inputs. The `operation_id` doubles as the agent's tool name where the agent uses it.

| Operation | Method and path | Used by |
|---|---|---|
| `health` | `GET /api/health` | dashboard |
| `list_claims` | `GET /api/claims` | dashboard |
| `get_claim` | `GET /api/claims/{claim_id}` | dashboard, agent tool |
| `get_policy` | `GET /api/policies/{policy_id}` | dashboard, agent tool |
| `get_claim_history` | `GET /api/customers/{customer_id}/history` | dashboard, agent tool |
| `get_policy_wording` | `GET /api/policy-wording` | agent tool |
| `get_instructions` | `GET /api/instructions` | dashboard, agent |
| `list_handlers` | `GET /api/handlers` | dashboard |
| `start_claim` | `POST /api/claims/{claim_id}/start` | agent |
| `add_step` | `POST /api/claims/{claim_id}/steps` | agent |
| `list_steps` | `GET /api/claims/{claim_id}/steps` | dashboard |
| `record_decision` | `POST /api/claims/{claim_id}/decision` | agent tool |
| `pay_claim` | `POST /api/claims/{claim_id}/pay` | agent tool |
| `sign_off_claim` | `POST /api/claims/{claim_id}/sign-off` | dashboard |
| `work_queue` | `POST /api/queue/work` | dashboard |

`get_claim_history` returns the customer's name and earlier claims, not their email, phone, address or date of birth. The agent needs the history, not the personal details.

### The data

SQLite through Python's built-in `sqlite3`, with no ORM: a handful of tables doesn't need one. The database file is `backend/undercover.db` (git ignores `*.db`), or the path in `DATABASE_PATH`, which the tests and the end-to-end run use for their own copies. It sits in `backend/` so it doesn't collide with the `undercover.db` left at the repo root by an earlier attempt.

- `claims`: the claim as seeded (stored as JSON), its status, and the decision, payout, reason, policy section, sign-off and payment
- `policies`, `customers`: seeded from `data/` as JSON
- `steps`: what the agent did on each claim, in order

On startup the backend creates the tables and seeds them from `data/` if they are empty. `uv run -m backend.seed` (also `npm run seed`) wipes the database and seeds it again, to reset the demo. Seeding reads `claims.json`, `policies.json`, `customers.json`, `handlers.json` and `company.json`, and nothing in `data/evals/` or `data/security/`.

## Phases

### Phase 1: The backend's records

Builds the database, the seeding and every read operation, so that later phases have real data to work on and the agent has something to read.

- `backend/db.py`: the schema, the connection, and seeding from `data/`
- `backend/seed.py`: the reset command
- `backend/main.py`: the read operations: `list_claims`, `get_claim`, `get_policy`, `get_claim_history`, `get_policy_wording`, `get_instructions`, `list_handlers`
- `backend/instructions.md`: a first version of the agent's instructions (finished in Phase 3)
- `list_claims` returns one row per claim for the queue table: id, customer name, type, submitted date, amount claimed, status, decision, payout and amount paid
- Pytest fixtures that give each test a fresh database in a temp folder
- `npm run seed` in `package.json`

Success criteria:

- [x] `uv run pytest -q backend` passes, with tests for every read operation, including 404s for unknown ids
- [x] `uv run -m backend.seed` creates `backend/undercover.db` with 25 claims, 50 policies and 49 customers
- [x] With `npm run dev` running, `GET /api/claims` returns 25 claims, all `waiting`
- [x] `GET /api/claims/CLM-1001` returns the full claim with its story, items and documents
- [x] `GET /api/customers/CUS-3001/history` returns Maya Patel's earlier claim CLM-0412 and no email, phone, address or date of birth
- [x] `GET /api/policy-wording` returns the text of `data/policy_wording.md`
- [x] A test checks that seeding reads no file under `data/evals/`, and `grep -ri evals backend agent` finds no mention outside that test
- [x] `/openapi.json` shows an `operation_id` and a one-line description on every operation, and no optional parameters
- [x] `npm run check:python` passes with coverage of at least 80%

### Phase 2: Decisions, payments and sign-off

Builds the operations that change a claim, with the $1,000 rule enforced here in the backend. This comes before the agent so the rules are tested on their own, without a model in the loop.

- `start_claim`: `waiting` to `in_progress`, clearing steps from any earlier run; 409 otherwise
- `add_step` and `list_steps`
- `record_decision`: takes `decision` (`approve`, `decline` or `refer`), `payout`, `reason` and `policy_section`. Only on a claim in progress. An approval over the limit moves the claim to `awaiting_signoff`; everything else moves it to `decided`. A decline or referral must have a payout of 0
- `pay_claim`: takes `amount`. Refuses with 409 if the claim isn't approved, is already paid, the amount isn't the approved payout, or the payout is over the limit without a sign-off
- `sign_off_claim`: takes `handler_id`. Only on a claim waiting for sign-off, by a handler who can approve over the limit. Records who signed off and when, pays the approved payout and moves the claim to `decided`
- The claim logic lives in `backend/claims.py`, so `main.py` stays a thin layer of routes

Success criteria:

- [x] Tests cover every transition and every refusal, including:
  - [x] Approve $420, pay $420: status `decided`, paid $420
  - [x] Approve $1,500, pay $1,500: 409, status `awaiting_signoff`, nothing paid
  - [x] Sign off by HND-01: status `decided`, paid $1,500, signed off by Dana Whitfield
  - [x] Pay a declined claim, pay twice, or pay a different amount: 409
  - [x] Decide a claim that isn't in progress, or decline with a payout: refused
  - [x] Sign off a claim that isn't waiting for sign-off, or with an unknown handler: refused
- [x] The same over-limit flow through `curl` against the running backend gives the same responses
- [x] `npm run check:python` passes with coverage of at least 80%

### Phase 3: The UnderCover Agent

Builds the agent on LangChain's `create_agent`, replacing the hello-world tool. It reads everything through the API and decides by calling `record_decision`, so the decision is structured and the backend validates it.

- `agent/main.py`:
  - Tools named after their operations: `get_claim`, `get_policy`, `get_claim_history`, `get_policy_wording`, `record_decision` and `pay_claim`. The agent gets no tool for signing off, starting claims or reading other customers' details
  - A refusal from the backend, such as a blocked payment, comes back to the model as the tool's result, so the agent can carry on and explain itself rather than crash
  - `run(claim_id, thread_id)`: fetches the instructions with `get_instructions`, calls `start_claim`, streams the agent, posts a step to `add_step` for each tool call and its outcome and for the agent's closing summary, and returns the final reply
  - The model stays as it is: `openai/gpt-6-luna` with low reasoning effort, or `MODEL_NAME` if set
- `agent/__main__.py`: `uv run -m agent CLM-1001` runs one claim against the running backend
- `backend/instructions.md`, written in full: read the claim, the policy, the history and the wording; check the trip dates, the plan's limits, the exclusions and the documents; work out the payout as section 10 of the wording says; refer when a document the wording asks for is missing or the claim needs a person's judgment; record the decision with a reason of two or three sentences and the section it rests on; pay an approved claim, knowing a payout over $1,000 waits for a handler

Success criteria:

- [x] `uv run pytest -q agent` passes with a stub model and the backend's `TestClient`, and no test calls a model. The tests cover:
  - [x] A scripted run that reads the claim, approves $420, pays, and leaves the claim `decided` and paid, with its steps recorded
  - [x] A scripted run that approves $1,500 and tries to pay: the payment is refused, the claim is `awaiting_signoff` and nothing is paid
  - [x] A scripted decline with a payout of 0
  - [x] The model choice from `MODEL_NAME`
- [x] With the backend running, `uv run -m agent CLM-1001` on the real model ends with a decision on CLM-1001, a reason of two or three sentences, a policy section, and its steps in `GET /api/claims/CLM-1001/steps` (one claim, a fraction of a cent)
- [x] `npm run check:python` passes with coverage of at least 80%

### Phase 4: Working the queue

Connects the agent to the backend so the dashboard can start it. One background thread works the waiting claims in order, so two runs never pick up the same claim.

- `backend/worker.py`: `work_queue` starts a background thread that calls `run` on each waiting claim in turn, and returns how many claims it will work. A second call while it's running gets a 409
- If a run fails, or ends without a decision, the claim goes back to `waiting` with a step that says so, and the queue carries on with the next claim
- The thread id for each run is the claim id plus a short random suffix

Success criteria:

- [x] Tests, with `run` replaced by a stub, check that every waiting claim is worked once, in order; that a second `work_queue` while running gets 409; and that a failing run puts its claim back to `waiting` with a step and the queue carries on
- [x] After `npm run seed`, `curl -X POST http://localhost:8000/api/queue/work` on the real model works through all 25 claims (about 25 runs, a few cents with GPT-6 Luna, or free with `MODEL_NAME=openrouter/free`)
- [x] Afterwards every claim is `decided` or `awaiting_signoff`, none is stuck in progress, every decision has a reason and a policy section, and no claim over $1,000 is paid without a sign-off
- [x] `npm run check:python` passes with coverage of at least 80%

### Phase 5: The dashboard's queue and instructions

Builds the queue page from the screen recipe in `docs/BRAND.md`, and the read-only instructions page. Routing is a small hook over the browser's history, since three pages don't need a router library.

- `dashboard/src/api.ts`: typed calls and types for the API
- `dashboard/src/styles.css`: the brand tokens and patterns, Outfit from Google Fonts in `index.html`
- `dashboard/src/format.ts`: $1,250.00, Jul 6, 2026, claim type labels
- Components: header with the Queue and Instructions pills and a refresh icon button, status chip, decision chip, status bar, ring chart (SVG), decisions bar, Next for sign-off panel, claims table
- The queue page: title row with the claim count and the "Work the queue" button; summary row with the status bar and the Waiting, For sign-off and Paid numbers; the main grid with the table across three columns and the three cards on the right, moving under the table below 1200px; an empty line in each card with nothing to show
- Clicking a row, or pressing Enter on it, opens the claim
- The page polls `list_claims` every two seconds
- The instructions page shows the text from `get_instructions`, read only

Success criteria:

- [x] Vitest tests, with `fetch` stubbed, cover the formatting, the chips, the status bar's counts and percentages (including "0 · 0%"), the empty states, the button calling `work_queue`, and the instructions page
- [x] `npm run check:ts` passes with coverage of at least 80%
- [x] In the browser with the Playwright MCP server, after `npm run seed`, the queue at 1440px wide shows 25 claims, the status bar reads "25 · 100%" under Waiting and "0 · 0%" in the other three, and the cards on the right show their empty lines
- [x] Every status is a filled chip in the exact status colors, every decision a tinted chip with its icon, and a claim with no decision shows "–"
- [x] Hovering a row turns it white with rounded corners and hides the dashed lines either side; tabbing to a row shows the same highlight
- [x] At 375px wide the page doesn't scroll sideways, the right-hand cards sit under the table, and the table scrolls inside its card
- [x] After a few claims are decided through the API, the page updates within two seconds without a reload
- [x] The Instructions pill shows the agent's instructions

### Phase 6: The claim page, sign-off and end-to-end tests

Builds the claim page, where a handler reads a claim in full, follows the agent's steps live and signs off a large payout. Then end-to-end tests cover the whole flow.

- The claim page at `/claims/CLM-1001`: the claim's story, items, documents and policy; the decision card with the decision chip, payout, reason and policy section; the payment and sign-off; the agent's steps, updating every two seconds while the claim is in progress
- On a claim waiting for sign-off, a handler picker and a "Sign off" Sunflower button that calls `sign_off_claim`
- End-to-end tests run their own backend and dashboard on ports 8001 and 5174 with their own database, seeded fresh on each run, so they never touch the dev database. `playwright.config.ts` sets this up and the Vite proxy reads the backend's address from `API_URL`
- The tests play the agent's part through the API, so they never call a model

Success criteria:

- [x] Vitest tests cover the claim page's sections, the steps list, and sign-off
- [x] Playwright tests pass:
  - [x] The queue loads with 25 waiting claims
  - [x] A claim approved at $420 and paid through the API shows as Decided and Approved with $420.00 in the queue, and its page shows the reason, the section and the steps
  - [x] A claim approved at $1,500 has its payment refused, shows as Waiting for sign-off and appears in the Next for sign-off panel; on its page a handler signs off, and it shows as Decided and paid $1,500.00
  - [x] The instructions page shows the instructions
  - [x] At 375px wide no page scrolls sideways
- [x] In the browser with the Playwright MCP server, clicking "Work the queue" with the real model shows a claim go In progress, its steps appear on its page while it works, and it ends Decided or Waiting for sign-off
- [x] `docs/STATUS.md` describes what's built and how to run it, and the root `README.md` is untouched
- [x] `npm run check` passes in full

## Not in this plan

- The claims manual. The agent works from the policy wording alone, as the spec says, so claims that need the manual's rules (the third claim in 12 months, wild animals, meals without receipts) may go differently from a handler's decision.
- Scoring the agent against `data/evals/`. The spec keeps the handlers' decisions for checking the agent's work, and `docs/PROCESS.md` says not to open that folder unless asked. I won't open it while building. Ask if you'd like the pilot's results scored against it once it's built.
- Sign-in, real payments and messages to customers.
- Anything from later briefs, such as the harness, durable state or the claims in `data/security/`.
