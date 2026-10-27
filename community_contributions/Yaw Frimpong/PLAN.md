# Plan: the claims pilot

The pilot from `docs/SPEC.md` has three parts. The backend holds UnderCover's claims and enforces the payment rule. The UnderCover Agent works each claim through that backend. The dashboard lets handlers watch the queue, read each claim with the agent's decision and reasons, follow the agent step by step, sign off large payouts and read the agent's instructions.

## How the pieces fit

```
dashboard (React, :5173) ──/api──▶ backend (FastAPI + SQLite, :8000) ◀──/api── agent (create_agent on OpenRouter)
                                        │
                                        └── seeded from data/*.json and data/policy_wording.md
```

- Only the backend touches the database and `data/`. The dashboard and the agent both go through its API, so every rule lives in one place and holds whatever a client sends.
- The agent's instructions are a file in the backend, `backend/instructions.md`. The API serves them. The agent loads them as its system prompt at the start of each run, and the dashboard shows the same text, read only.
- As the agent works, it records each step through the API: its messages, each tool call and each result. The dashboard asks for updates every 2 seconds, so handlers see the steps as they happen.

## The claim's life

```
waiting ──start──▶ in_progress ──decide──▶ decided                              decline, refer, or approve up to $1,000.00
                               └─────────▶ waiting_for_sign_off ──sign off──▶ decided    approve over $1,000.00; the sign-off pays
```

| Status | Label | Color |
|---|---|---|
| `waiting` | Waiting | Cerulean |
| `in_progress` | In progress | Marigold |
| `waiting_for_sign_off` | Waiting for sign-off | Coral |
| `decided` | Decided | Sea Green |

The status names follow the spec's own words. A referral is a decision, so a referred claim is Decided with the decision Refer. Decisions use Sea Green for Approve, Marigold for Refer and Coral for Decline. Raspberry is kept for alerts, such as a refused payment.

### The payment rule

The spec says the system must block a payment over $1,000 until a handler signs off, even if the agent tries to pay. The backend's `pay_claim` operation enforces this, so no prompt or model can get around it:

- A claim can be paid only after an Approve decision, only for the approved payout, and only once. Anything else returns 409.
- A payout over the limit returns 403 `A payout over $1,000.00 needs a handler's sign-off`. The limit, $1,000.00, comes from `data/company.json`. A payout of exactly $1,000.00 needs no sign-off, because the rule says "over".
- A handler's sign-off makes the payment itself, so nobody has to come back later to pay. Only a handler with `can_approve_over_limit` can sign off. All three handlers can today, but the check reads the flag.

No money moves. A payment is a record on the claim with its amount and date.

## The API

Every operation has an `operation_id` equal to its function name, a one-line docstring and no optional inputs, as `docs/TECH_STACK.md` requires. A test walks the OpenAPI schema and fails if any operation breaks those rules.

| Operation | Route | Used by |
|---|---|---|
| `health` | `GET /api/health` | e2e |
| `list_claims` | `GET /api/claims` | dashboard, agent CLI |
| `get_claim` | `GET /api/claims/{claim_id}` | agent, dashboard |
| `get_policy` | `GET /api/policies/{policy_id}` | agent, dashboard |
| `get_customer` | `GET /api/customers/{customer_id}` | dashboard |
| `get_claim_history` | `GET /api/customers/{customer_id}/claim-history` | agent |
| `get_policy_wording` | `GET /api/policy-wording` | agent |
| `get_instructions` | `GET /api/instructions` | agent, dashboard |
| `list_handlers` | `GET /api/handlers` | dashboard |
| `start_claim` | `POST /api/claims/{claim_id}/start` | agent |
| `record_step` | `POST /api/claims/{claim_id}/steps` | agent |
| `list_steps` | `GET /api/claims/{claim_id}/steps` | dashboard |
| `decide_claim` | `POST /api/claims/{claim_id}/decision` | agent |
| `pay_claim` | `POST /api/claims/{claim_id}/payment` | agent |
| `sign_off_claim` | `POST /api/claims/{claim_id}/sign-off` | dashboard |

Errors: 404 for an unknown id, 409 when the claim's state doesn't allow the operation, 422 for an invalid input, and 403 for a payment that needs a sign-off or a handler who can't give one.

## Choices to review

The documents leave these calls to me. Tell me if you want any of them changed before I build.

1. **The agent runs from the command line.** `uv run -m agent` works the queue and `uv run -m agent CLM-1001` works one claim. The spec asks for the team to see the agent at work, not to start it, so the dashboard has no run button. The queue command works every claim that is waiting or in progress, in order. If a run crashes, running the command again picks up where it stopped.
2. **The agent can change only the claim it was given.** Its `decide_claim` and `pay_claim` tools are built for each run with the claim id already filled in, so the model can't decide or pay a different claim, even by mistake. The read tools take ids, because the agent finds the policy and customer ids on the claim.
3. **The agent sees the customer's claim history, not their personal details.** `get_claim_history` returns only the earlier claims on the customer's record. The dashboard's `get_customer` returns the full record for handlers. One customer, Oliver Grant (`CUS-3005`), has two claims in the queue, `CLM-1005` and `CLM-1006`. His history shows only the earlier claims on his record, so neither claim's outcome depends on which one the agent works first.
4. **The decision cites a section by number.** `decide_claim` takes the section of the wording the decision rests on as a number from 1 to 12, and the backend rejects any other number. The claim page then shows that section's title and wording beside the agent's reason. The spec asks for "the relevant section of the policy", and showing the clause itself lets a handler check the reason against it.
5. **The policy comes with its plan's limits.** `get_policy` returns the policy together with its plan's name, limits and deductible from `data/plans.json`, and the names of its add-ons. The agent works out payouts from exact numbers, and the dashboard shows "UnderCover Premium" rather than `premium`. The wording's table has the same numbers.
6. **The full policy wording.** The agent works from `data/policy_wording.md`, version 2026.1. `data/policy_wording_short.md` is for the labs. The claims manual, `data/knowledge.json`, `data/security/` and `data/evals/` stay out of the product entirely.
7. **SQLite through Python's built-in `sqlite3`**, with no new dependency. Policies, customers, plans and handlers are stored as JSON records keyed by id. Claims have columns for their status, decision, payment and sign-off, and steps have a table of their own. The database file is `backend/undercover.db`, set by `UNDERCOVER_DB` (your `.env` already uses `DATABASE_URL` for something else). The backend seeds an empty database on startup, and `uv run -m backend.seed` resets it.
8. **Polling, not a live connection.** The dashboard asks for updates every 2 seconds. That's fast enough to follow the agent and much simpler than server-sent events or websockets.
9. **No router library.** The dashboard has three pages, `/`, `/claims/<id>` and `/instructions`, chosen from the URL path, with plain links between them.
10. **The end-to-end tests run on their own backend, dashboard and database** (ports 8001 and 5174, with `e2e/undercover.db`). That way `npm run check` never wipes the claims the agent has decided on your dev database.
11. **Re-running a claim.** Starting a claim that's waiting or in progress clears its earlier steps and starts again. A claim with a decision can't be started again until you reseed.

## Not in this plan

- The claims manual, sign-in, real payments and messages to customers, as the spec says.
- Starting the agent from the dashboard.
- Scoring the agent against `data/evals/`. The spec keeps that for later. Nothing in the product reads that folder, and I won't open it unless you ask.

## Phase 1: the data and the read operations

**Builds:** the SQLite schema and the seed (`backend/db.py`, `backend/seed.py`), the response models, and the read operations: `list_claims`, `get_claim`, `get_policy`, `get_customer`, `get_claim_history`, `get_policy_wording` and `list_handlers`. The seed reads named files only: `claims.json` (where status `open` becomes `waiting`), `policies.json`, `customers.json`, `plans.json`, `handlers.json` and `company.json` for the approval limit. Tests run on a temporary database.

**Why first:** everything else reads through these operations, and the seed gives every later phase a known starting point.

- [x] `uv run -m backend.seed` prints `Seeded 25 claims, 50 policies, 49 customers, 3 plans and 3 handlers.` and creates `backend/undercover.db`
- [x] With no database file, starting the backend creates and seeds one. With a seeded database, a restart keeps its data.
- [x] `GET /api/claims` returns 25 claims, `CLM-1001` to `CLM-1025`, all `waiting`, each with the customer's name, the claim type, the submitted date and the amount claimed
- [x] `GET /api/claims/CLM-1001` returns the full claim: the story, 3 items, 4 documents, `amount_claimed` 420.0, and `decision`, `payment` and `sign_off` all null
- [x] `GET /api/claims/CLM-9999` returns 404 with `Claim CLM-9999 not found`
- [x] `GET /api/policies/POL-2001` returns the Premium policy for Rome, June 10 to 18, 2026, with Maya Patel as the traveler and the Premium limits, such as $800.00 for Trip Delay and a $50.00 deductible
- [x] `GET /api/customers/CUS-3001` returns Maya Patel with her contact details and one earlier claim, `CLM-0412`. `GET /api/customers/CUS-3001/claim-history` returns that claim and no name, email, phone, date of birth or address.
- [x] `GET /api/policy-wording` returns version `2026.1` and the text of `data/policy_wording.md`
- [x] `GET /api/handlers` returns Dana Whitfield, Marcus Oyelaran and Priya Raman
- [x] A test fails if any operation lacks an `operation_id` equal to its function name, lacks a one-line docstring, or has an optional parameter or body field
- [x] `grep -rnE "evals|security|claims_manual|knowledge" backend agent dashboard/src` finds nothing
- [x] Running `uv run -m backend.seed` while the backend is running resets the data without an error
- [x] `npm run check:python` passes, with coverage at 80% or more

## Phase 2: the claim workflow and the payment rule

**Builds:** `start_claim`, `record_step`, `list_steps`, `decide_claim`, `pay_claim`, `sign_off_claim` and `get_instructions`, with the first version of `backend/instructions.md` (draft below).

- A step has a kind (`message`, `tool_call` or `tool_result`), a name, its content and a time.
- A decision has the decision (`approve`, `decline` or `refer`), the payout, the reason, the policy section and a time. `get_claim` adds the section's title and wording.
- Amounts must be zero or more with at most two decimal places. A payout can't be more than the amount claimed, and a decline or a referral pays $0.00.

**Why now:** the payment rule is the spec's one hard requirement. Putting it in the backend, with a test for each case, means it holds whatever the agent does, and Phase 3 gets a finished API to work against.

Each criterion is a pytest test, and I'll also check the main ones with `curl` against a freshly seeded dev backend:

- [x] `GET /api/instructions` returns the text of `backend/instructions.md`
- [x] `start_claim` on `CLM-1001` sets it to `in_progress`. Starting it again clears its steps. Starting a decided claim, or one waiting for sign-off, returns 409.
- [x] `record_step` stores steps and `list_steps` returns them in order. An unknown kind returns 422. Recording on a waiting claim returns 409. Recording on a decided claim works, because the agent's last message comes after its decision.
- [x] `decide_claim` on a claim that hasn't been started returns 409
- [x] Approving `CLM-1001` for $420.00 under section 3 sets it to `decided`, and `get_claim` shows the section as `3. Trip Delay` with its wording. Deciding it again returns 409.
- [x] Each of these returns 422: a decline or a referral with a payout other than $0.00, a payout above the amount claimed, a negative amount, an amount with three decimal places, and section 13
- [x] `pay_claim` for $420.00 records the payment. Paying again returns 409. Paying a different amount returns 409. Paying a declined, referred or undecided claim returns 409.
- [x] Approving a claim for $1,500.00 sets it to `waiting_for_sign_off`. Then `pay_claim` for $1,500.00 returns 403 with `A payout over $1,000.00 needs a handler's sign-off`, and the claim still has no payment.
- [x] Approving a claim for exactly $1,000.00 sets it to `decided`, and it can be paid
- [x] `sign_off_claim` by `HND-01` sets the claim to `decided` and records both the sign-off and a $1,500.00 payment. Signing off again returns 409. Signing off a claim that isn't waiting for sign-off returns 409. An unknown handler returns 404, and a handler without `can_approve_over_limit` returns 403.
- [x] `GET /api/claims` shows each claim's decision, payout and whether it's paid
- [x] `npm run check:python` passes, with coverage at 80% or more

### Draft instructions for the agent

The instructions state the goal and the rules, not a script of tool calls. The tools' own descriptions say what each one does.

```
You are the UnderCover Agent. You decide travel insurance claims for UnderCover
Travel Insurance the way one of its claims handlers would, by the policy
wording alone.

For the claim you're given, read the claim first: it names the customer's
policy and the customer. Then read the policy, the customer's claim history
and the policy wording, and decide:

- Approve when the wording covers the loss and the claim meets its conditions.
  Work out the payout item by item as section 10 describes, using the plan's
  limits and deductible.
- Decline when the wording excludes the loss, or the claim fails a condition
  of the benefit.
- Refer when the claim needs a person's judgment or more information, such as
  a required document that's missing or documents that contradict the story.

Record your decision with decide_claim: the payout ($0.00 unless you approve),
the reason in two or three plain sentences, and the number of the section of
the wording the decision rests on.

If you approve a payout of $1,000.00 or less, pay it with pay_claim. A larger
payout waits for a handler's sign-off, so don't pay it.

Amounts are in US dollars, written like $1,250.00.
```

## Phase 3: the UnderCover Agent

**Builds:** `agent/main.py`, rebuilt around the claim, and `agent/__main__.py` for the command line.

- The tools are `get_claim`, `get_policy`, `get_claim_history`, `get_policy_wording`, `decide_claim` and `pay_claim`. Each is one call to the backend's API and returns the response text, errors included. A refused payment reaches the model as the 403 message, so it can carry on instead of crashing.
- `run(claim_id, thread_id)` starts the claim, loads the instructions from `GET /api/instructions`, builds the agent with `create_agent` and streams its updates. It records each model message, tool call and tool result as a step as it happens.
- `uv run -m agent` works every claim that's waiting or in progress, in order, and prints one line per claim, such as `CLM-1001: approve, $420.00, paid`. `uv run -m agent CLM-1001` works one claim. Each run gets a fresh thread id.
- The model stays as it is: `openai/gpt-6-luna` at low reasoning effort, or `MODEL_NAME` if set.

**Why this way:** the agent holds no business rules and no data. It reads and acts through the same API as the dashboard, as the tech stack asks. Recording steps from the stream keeps this first agent small. I checked that `create_agent` streams one `model` update per model turn and one `tools` update per tool result, which are exactly the steps the dashboard shows.

- [x] Tests with a stub model run the agent against the backend in-process:
  - [x] `CLM-1001`: the four reads, approve for $420.00 and pay. The claim ends `decided` and paid, with its steps recorded in order.
  - [x] An approval for $1,500.00 where the stub then tries to pay anyway: the tool returns the 403 message to the model, the run finishes, and the claim is `waiting_for_sign_off` with no payment
  - [x] A decline and a referral: both `decided`, neither paid
  - [x] The system prompt is the text from `GET /api/instructions`
  - [x] `decide_claim` and `pay_claim` have no claim id input and act on the run's claim
  - [x] A run that ends without a decision leaves the claim `in_progress`, and the command line says `CLM-1001 ended without a decision.`
  - [x] `uv run -m agent` works only the waiting and in-progress claims, in order
  - [x] `uv run -m agent CLM-1001` on a decided claim prints `CLM-1001 is already decided.` and stops
- [x] `grep -rnE "sqlite3|data/|^(from|import) backend" agent --include=*.py --exclude-dir=tests` finds nothing, because the agent reaches everything through the API. (Anchored to the start of a line, because `from agent.main import backend` imports the agent's own HTTP client.)
- [x] Live, with the real model and `npm run dev` running: `uv run -m agent CLM-1001` prints its line, and `GET /api/claims/CLM-1001` shows a decision with a two or three sentence reason and a section. If it's an approval of $1,000.00 or less, it's paid.
- [x] Live: `uv run -m agent CLM-1003` ($3,800.00 of emergency medical). If the agent approves over $1,000.00, the claim is `waiting_for_sign_off` with no payment, and any attempt to pay shows in its steps as refused.
- [x] `npm run check:python` passes, with coverage at 80% or more

## Phase 4: the dashboard's brand, queue and instructions

**Builds:**

- The brand from `docs/BRAND.md` as CSS variables, with light and dark mode following the system setting, and the three Google Fonts
- A header with links to Claims and Agent instructions
- The queue page and the instructions page
- `api.ts`, with types and a fetch function for every operation the dashboard uses
- A polling hook that refreshes every 2 seconds
- Formatting for money (`$1,250.00`), dates (`Jun 24, 2026`) and labels (`trip_delay` becomes `Trip delay`)

The skeleton's health page goes, and its end-to-end test becomes a test of the queue.

**Why now:** the queue is the handlers' home page. The brand, the API client and the polling built here are what the claim page in Phase 5 is made from.

- [x] The queue page lists the 25 claims. Each row shows its id (in JetBrains Mono), the customer, the type, the submitted date, the amount claimed and a status badge, plus the decision, the payout and whether it's paid once decided.
- [x] Counts at the top show how many claims are in each of the four statuses
- [x] Each row links to `/claims/<id>`
- [x] With the queue open, `curl -X POST localhost:8000/api/claims/CLM-1002/start` turns that row to In progress within 3 seconds, with no reload
- [x] The instructions page shows the text of `backend/instructions.md`, with nothing to edit
- [x] With the backend stopped, the page says `The backend isn't reachable.`, and it recovers by itself when the backend is back
- [x] Vitest covers the queue, the instructions page, the polling and the formatting. `npm run check:ts` passes, with coverage at 80% or more.
- [x] `npm run e2e` passes with the queue test in place of the health test
- [x] In the browser, with the Playwright MCP server, the queue and the instructions page at `http://localhost:5173` match the brand in both modes. Light mode has a `#F0F4F5` page with white panels, and dark mode has a `#04232E` page with black panels. Both use the brand fonts and rounded panels with no outline, with no border on one edge of a panel and no line across the top of the page.

## Phase 5: the claim page, live steps and sign-off

**Builds:** `/claims/<id>`, refreshing every 2 seconds, with:

- The claim in full: the summary, the status, the story, the items with their amounts, the amount claimed, and each document with its type and text
- The policy: the plan and its limits, the add-ons, the purchase date, the trip and its cost, and the travelers
- The customer: name, contact details, customer since, and the earlier claims
- The agent's decision: the decision, the payout, the reason, and the policy section's title with its wording folded away to open on a click. Under it, the payment: paid, waiting for a handler's sign-off, or not paid yet.
- When the claim is waiting for sign-off: a choice of handler and a button such as "Sign off and pay $1,500.00"
- The agent's steps in order: its messages, each tool call with its inputs, and each result folded away to open on a click

**Why this way:** this page is where a handler checks the agent's work, so it puts the decision and the clause it rests on next to the evidence. Signing off is the one thing a handler does here, and the backend checks it whatever the page sends.

- [x] `/claims/CLM-1001` shows the story, the 3 items, the 4 documents, the Premium policy for the Rome trip and Maya Patel's earlier claim `CLM-0412`
- [x] Before a decision, the decision panel says `The agent hasn't decided this claim yet.`
- [x] After a decision set through the API, it shows the decision badge, the payout, the reason and `3. Trip Delay`, whose wording opens on a click. The payment line reads `Not paid yet` before payment and `Paid $420.00 on <date>` after.
- [x] A claim put into `waiting_for_sign_off` through the API shows the handler choice and the sign-off button. Choosing Dana Whitfield and signing off turns the page to Decided with `Paid $1,500.00, signed off by Dana Whitfield on <date>`. (Checked on `CLM-1010` for $1,200.00, since it claims $1,350.00 and the backend refuses a payout above the amount claimed.)
- [x] Steps recorded through the API appear on the page without a reload
- [x] `/claims/CLM-9999` says `Claim CLM-9999 not found.`
- [x] Vitest covers each state of the decision panel, the sign-off and the steps. `npm run check:ts` passes, with coverage at 80% or more.
- [x] In the browser, with the Playwright MCP server: `/claims/CLM-1004` is open while `uv run -m agent CLM-1004` runs live, and the steps arrive one by one, then the decision. The page reads well in light and dark mode.

## Phase 6: end-to-end tests and a run over the queue

**Builds:**

- Playwright on its own ports and database: a backend on 8001 with `UNDERCOVER_DB=e2e/undercover.db`, reseeded each time it starts, and a dashboard on 5174 that sends `/api` to it. The dashboard's proxy target comes from an environment variable, with 8000 as the default.
- End-to-end tests that each work on their own claim and set it up through the API, so no model is called
- Then the agent works the whole queue live, and `docs/STATUS.md` gets its final update

**Why this way:** the end-to-end tests prove the pieces work together in a real browser, and their own database means `npm run check` leaves your dev data alone. The live run is the pilot doing its job on all 25 claims.

- [x] End-to-end tests pass for:
  - [x] the queue, with 25 claims and their statuses
  - [x] a claim page showing the claim in full
  - [x] steps recorded through the API appearing on the claim page without a reload
  - [x] a payment over $1,000.00 refused by the API with 403, and the page showing the claim waiting for sign-off with no payment
  - [x] a handler signing off in the browser, and the claim becoming Decided and paid
  - [x] the instructions page, read only
- [x] With `npm run dev` running and a claim decided on the dev database, `npm run e2e` passes and that claim is still decided afterwards
- [x] Live: `uv run -m backend.seed`, then `uv run -m agent` works all 25 claims. Afterwards every claim is Decided or Waiting for sign-off with a reason and a section. A short script over the API confirms that no payout over $1,000.00 has been paid without a sign-off, and every approval of $1,000.00 or less has been paid. I'll report how many claims were approved, declined and referred, and re-run any claim the model left unfinished. (Result: 16 approved, 7 declined and 2 referred. `CLM-1018` was re-run once, because the model wrote its decision as a message instead of calling `decide_claim`.)
- [x] In the browser, with the Playwright MCP server, a final walk in light and dark mode: the queue, a claim with each kind of decision, a sign-off and the instructions
- [x] `docs/STATUS.md` says what's built and how to run it
- [x] `npm run check` passes: ruff, pyright, pytest, Prettier, ESLint, tsc, vitest and Playwright

## What the live runs cost

The live runs call the model on OpenRouter: two claims in Phase 3, one in Phase 5 and all 25 in Phase 6. To spend nothing, set `MODEL_NAME=openrouter/free` in `.env` first. Free models are less reliable at calling tools, so expect to re-run a few claims.
